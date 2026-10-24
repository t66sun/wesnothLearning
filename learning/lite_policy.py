"""Frozen CPU tensor policies and standard-era initial states for lite workers."""
import hashlib
import json
import math
from pathlib import Path
import random
from collections import OrderedDict
from .rowpack import compact_row

_models=OrderedDict()


def game_spec(job,rules):
    from .common import ROOT
    import params
    board=job.get('map_override')
    if board is None:
        board=json.loads((ROOT/'vendor/arena/maps'/f'arena{len(job["bots"])}.json').read_text(encoding='utf-8'))
    factions=job['factions'];sides=[];units=[]
    if len(factions)!=len(board['starts']): raise ValueError('factions/start positions do not match')
    width=int(board.get('width',len(board['terrain'][0])));height=int(board.get('height',len(board['terrain'])))
    for side,faction in enumerate(factions,1):
        index=params.FACTIONS.index(faction);unit_type=params.LEADERS[index];definition=rules['units'][unit_type]
        x,y=board['starts'][side-1];team=str(job['teams'][side-1]) if job.get('teams') else str(side)
        sides.append(dict(id=side,team=team,faction=faction,gold=params.START_GOLD,base_income=2,recruit=params.RECRUITS[index].split(','),
            fog=job.get('fog',True),shroud=job.get('shroud',False),share_view=job.get('share_view',True),share_maps=job.get('share_maps',True)))
        units.append(dict(id=f'leader_{side}',unit_type=unit_type,side=side,pos=(y-1)*width+x-1,
            hp=definition['hp'],moves=definition['moves'],attacks_left=1,xp=0,leader=True,status=[],traits=[]))
    return dict(width=width,height=height,terrain=[t for row in board['terrain'] for t in row],sides=sides,units=units,
        village_owner={},seed=job['seed'],max_turns=job.get('max_turns',60),experience_modifier=params.XP_MODIFIER,
        allow_approximate=job.get('allow_approximate',False))


def is_astra(bot): return bot in ('astra','gpt6astra') or Path(str(bot)).stem=='gpt6astra'


class FrozenPolicies:
    def __init__(self,job):
        self.job=job;self.histories={};self.models={};self.rng={};self.modes={};self.memory_contexts={}
        from .formats import infer_format
        self.format=job.get('format') or job.get('meta',{}).get('format') or infer_format(dict(bots=job['bots'],teams=job.get('teams')))
        from .export import load_model
        from .common import sha256
        for side,bot in enumerate(job['bots'],1):
            self.rng[side]=random.Random(job['seed']+side*100003)
            self.histories[side]=[]
            if is_astra(bot): continue
            addon=Path(bot);path=addon.parent/'model.pt'
            if not path.is_file(): raise ValueError('lite needs frozen tensor weights beside exported addon: '+str(path))
            key=(str(path.resolve()),sha256(path),self.format)
            if key not in _models:
                model,_=load_model(path,self.format,'cpu');model.eval();_models[key]=model
                while len(_models)>4: _models.popitem(last=False)
            _models.move_to_end(key)
            self.models[side]=_models[key]
            config=addon/'lua/config.lua'
            text=config.read_text(encoding='utf-8') if config.exists() else ''
            self.modes[side]='["mode"]="sample"' in text or '["mode"] = "sample"' in text

    def choose(self,row,side,bootstrap=False):
        import torch
        from .model import batch
        history=self.histories[side];model=self.models[side]
        key=(len(history),row['turn'])
        with torch.no_grad():
            cached=self.memory_contexts.get(side)
            if cached is None or cached[0]!=key:
                zero=next(model.parameters()).new_zeros(1,model.scene_width)
                memory=model.context(zero,[history],[row['turn']])[:,model.scene_width:]
                cached=(key,memory);self.memory_contexts[side]=cached
            tensors=batch([row],'cpu',include_history=False)
            tensors[5]['memory_context']=cached[1]
            logits,value=model(*tensors)
        if bootstrap: return float(value[0])
        scores=logits[0,:len(row['candidates'])].tolist();best=max(range(len(scores)),key=scores.__getitem__)
        probabilities=[math.exp(v-scores[best]) for v in scores];total=sum(probabilities);probabilities=[p/total for p in probabilities]
        stochastic=self.modes[side]
        chosen=self.rng[side].choices(range(len(scores)),weights=probabilities,k=1)[0] if stochastic else best
        return dict(choice=chosen,log_probability=math.log(max(1e-300,probabilities[chosen])),value=float(value[0]))

    def commit(self,side,row,outcome):
        if not outcome.get('committed',outcome.get('execution',{}).get('changed',False)): return
        history=self.histories[side]
        if not history or history[-1]['turn']!=row['turn']:
            write=dict(outcome['memory_write'],turn=row['turn'],candidates=[])
            history.append(compact_row(write))
