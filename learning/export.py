from pathlib import Path
import json
import shutil
import torch
from .common import ROOT, write_json, sha256
from .checkpoints import validate_checkpoint
from .features import schema
from .model import Policy,ARCHITECTURE
from .formats import FORMATS
from .weight_export import weight_source
from .sequence_parity import verify_numerics, verify_shard_numerics
import addons
import native

def lua_parameters(model):
    layers = dict(architecture_id='relational_v5',unit_embedding=model.unit_embedding.weight.detach().cpu().tolist())
    for name, group in [('opponent', model.opponent), ('scorer', model.scorer), ('value', model.value)]:
        layers[name] = [dict(weight=l.weight.detach().cpu().tolist(), bias=l.bias.detach().cpu().tolist())
                        for l in group if isinstance(l, torch.nn.Linear)]
    def linear(layer): return dict(weight=layer.weight.detach().cpu().tolist(),bias=layer.bias.detach().cpu().tolist())
    for name in ('entity','conv1','conv2','local','summary','memory_query','memory_key','memory_value'):
        layers[name]=linear(getattr(model,name))
    layers['entities']=[{name:linear(getattr(block,name)) for name in ('q','k','v','out','ff1','ff2')} for block in model.entities]
    layers['gru']={name:param.detach().cpu().tolist() for name,param in model.gru.named_parameters()}
    return layers


def compact_lua(value):
    if isinstance(value,float): return format(value,'.17g')
    if isinstance(value,(list,tuple)): return '{'+','.join(map(compact_lua,value))+'}'
    if isinstance(value,dict): return '{'+','.join('['+native.lua(k)+']='+compact_lua(v) for k,v in value.items())+'}'
    return native.lua(value)


def write_config(addon, mode, version, formats):
    settings = dict(mode=mode, version=version, formats=list(formats))
    (addon / 'lua' / 'config.lua').write_text('return ' + native.lua(settings) + '\n', encoding='utf-8')


def export(models, destination, name='NeuralArena', mode='greedy', version='untrained', package=True, evaluation=None,
           identity=None):
    """A single-format support export is permitted; a delivery requires all three."""
    if isinstance(models, Policy): models={models.format_name:models}
    if not models or any(k not in FORMATS or v.format_name!=k for k,v in models.items()): raise ValueError('model format mismatch')
    if package and set(models)!=set(FORMATS): raise ValueError('delivery requires three independent models')
    addons.valid_name(name)
    if mode not in ('greedy','sample','rule'): raise ValueError('invalid policy mode')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    addon = destination / name
    if addon.exists():
        raise FileExistsError(addon)
    (addon / 'lua').mkdir(parents=True)
    for filename, content in zip(('_main.cfg', 'ai.cfg'), addons.configuration(name)):
        (addon / filename).write_text(content, encoding='utf-8')
    write_json(addon / 'arena.json', dict(schema=2, id=name, entry='lua/bot.lua'))
    for src in (ROOT / 'lua').glob('*.lua'):
        content = src.read_text(encoding='utf-8').replace('@ADDON@', name)
        (addon / 'lua' / src.name).write_text(content, encoding='utf-8')
    weight_manifest={}
    for fmt,model in models.items():
        path=addon/'lua'/f'weights_{fmt}.lua'
        path.write_text(weight_source(lua_parameters(model)),encoding='utf-8')
        weight_manifest[fmt]=dict(version=version.get(fmt) if isinstance(version,dict) else version,
            parameters=sum(p.numel() for p in model.parameters()),sha256=sha256(path),
            evaluation=(evaluation or {}).get(fmt,'not_evaluated'),**(identity or {}))
    (addon / 'lua' / 'features.lua').write_text('return ' + native.lua(schema()) + '\n', encoding='utf-8')
    write_config(addon, mode, version, models)
    (addon / 'README.md').write_text('三个独立网络原生 AI。权重与评测状态见交付清单。\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'vendor/arena/LICENSE', addon / 'LICENSE')
    if package:
        # The 16 MiB SDK cap applies to submitted archives. Internal support and
        # policy directories used by the native collector are deliberately not
        # submissions; they may exceed it while carrying three live models.
        addons.validate(addon)
        archive = addons.pack(addon, destination / (name + '.zip'))
        write_json(destination / 'export.json', dict(id=name,version=version,sha256=sha256(archive),features=schema(),
                   architecture=ARCHITECTURE,models=weight_manifest,identity=identity))
    else: write_json(destination/'export.json',dict(models=weight_manifest,features=schema(),
                    architecture=ARCHITECTURE,identity=identity))
    return addon


def load_model(checkpoint, format_name, device='cpu'):
    state = validate_checkpoint(torch.load(checkpoint, map_location=device, weights_only=False), format_name)
    model = Policy(format_name).to(device)
    model.load_state_dict(state['model'])
    return model, state


def export_checkpoints(checkpoints, destination, name='NeuralArena', evaluation=None, audit_records=None, *,
                       audit_paths=None, audit_workers=1):
    if set(checkpoints)!=set(FORMATS): raise ValueError('provide duel, ffa4 and team2v2 checkpoints')
    models={};versions={};errors={};identities={}
    for fmt,path in checkpoints.items():
        models[fmt],state=load_model(path,fmt)
        identity={key:state.get(key) for key in ('engine','engine_version','rng_version','combat_version',
                                                   'teacher','teacher_profile','teacher_source_sha256')}
        if not all(identity.values()):
            raise ValueError('checkpoint lacks combat or teacher profile identity; old weights are explicit initialization only: '+fmt)
        if identity['engine']=='lite':
            from .adapters import ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION
            from .teachers import identity as teacher_identity
            expected=dict(engine='lite',engine_version=ENGINE_VERSION,rng_version=RNG_VERSION,
                          combat_version=COMBAT_VERSION,**teacher_identity())
        elif identity['engine']=='native':
            expected=dict(engine='native',engine_version='1.18.8',rng_version='native-1.18.8',
                          combat_version='native-1.18.8',teacher='gpt6astra',teacher_profile='native',
                          teacher_source_sha256='native-1.18.8')
        else:
            raise ValueError('unsupported checkpoint engine identity: '+fmt)
        if identity!=expected or (identities and identity!=next(iter(identities.values()))):
            raise ValueError('checkpoint combat or teacher identity differs: '+fmt)
        identities[fmt]=identity
        if state.get('runner',{}).get('version',0)<=0 and state.get('metrics',{}).get('updates',0)<=0:
            raise ValueError('delivery requires a trained checkpoint, not initial support weights: '+fmt)
        if audit_paths is not None:
            errors[fmt]=verify_shard_numerics(models[fmt],audit_paths.get(fmt,()),audit_workers)
        elif audit_records and audit_records.get(fmt):
            errors[fmt]=verify_numerics(models[fmt],audit_records[fmt])
        else:
            raise ValueError('delivery export requires actual current-schema sequence parity data for '+fmt)
        versions[fmt]=dict(checkpoint_sha256=sha256(path),version=state.get('runner',{}).get('version',state.get('version','unknown')))
    addon=export(models,destination,name=name,version=versions,evaluation=evaluation)
    manifest=json.loads((Path(destination)/'export.json').read_text(encoding='utf-8'))
    for fmt,error in errors.items():
        manifest['models'][fmt].update(identities[fmt], python_lua_max_error=error)
    write_json(Path(destination)/'export.json',manifest)
    return addon
