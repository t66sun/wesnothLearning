"""One authorized, checkpoint-preserving migration; never edits the parent run."""
import copy
from datetime import datetime
import json
from pathlib import Path
import shutil
import time
from zoneinfo import ZoneInfo
import torch
from learning.common import ROOT,read_json,write_json,sha256
from learning.manifest import freeze,verify_frozen,tree_hashes
from learning.export import load_model
from learning.experiment import run_lock,FormatExperiment
from learning.features import select_rules,schema
from learning.phases import request_phase

PARENT=Path('/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022/runs/v5_lite18h_20261024_003512')
DEST=ROOT/'runs/v5_lite_resume_20261024_1420'
EXPECTED={'duel':'718b9bb17d078826f7c729e3c557934ec1857e373e0387df6cec766c3cf813ff','ffa4':'7755cedaea876a201e6816bf166045802c87844c1e47c7bae1fc2e88b4e37c6a','team2v2':'0a9638c797e3bd648561d15160d2d3b36ca59de9c6fcc5721f34a65b24d01779'}

def equal(a,b):
    if isinstance(a,torch.Tensor):assert torch.equal(a,b);return
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:equal(a[k],b[k])
    elif isinstance(a,(list,tuple)):
        assert type(a)==type(b) and len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    else:assert a==b,(a,b)

def main():
    with run_lock(PARENT):
        old=read_json(PARENT/'manifest.json');oldhash=sha256(PARENT/'manifest.json')
        assert oldhash=='43cd83777cd213771cf7e574143a848020dcd975b073763c143fe66048de1bf3'
        oldclock=read_json(PARENT/'clock.json')
        for folder,hashes in old['source'].items():
            assert tree_hashes(PARENT.parent.parent/folder)==hashes,('parent source differs',folder)
        select_rules(old['config']['rules_dir'])
        # Architecture, vocabulary, optimizer and gameplay semantics remain compatible.
        for name in ['model.py','features.py','train.py','schedule.py','phases.py']:
            assert (PARENT.parent.parent/'learning'/name).read_text()==(ROOT/'learning'/name).read_text(),name
        for name in ['candidates.lua','spatial.lua','observation.lua','memory.lua','rewards.lua']:
            assert (PARENT.parent.parent/'lua'/name).read_text()==(ROOT/'lua'/name).read_text(),name
        sources={}
        for fmt,digest in EXPECTED.items():
            p=PARENT/fmt/'latest.pt';assert sha256(p)==digest
            model,saved=load_model(p,fmt)
            assert saved['manifest_sha256']==oldhash
            optimizer=torch.optim.Adam(model.parameters(),lr=old['config']['learning_rate'])
            optimizer.load_state_dict(saved['optimizer'])
            assert len(optimizer.state)>0 and torch.isfinite(torch.cat([p.detach().flatten() for p in model.parameters()])).all()
            for slot in optimizer.state.values():
                assert all(not isinstance(v,torch.Tensor) or torch.isfinite(v).all() for v in slot.values())
            from learning.train import restore_rng
            restore_rng(saved)
            r=saved['runner'];assert not r['pending_train'] and not r['pending_validation']
            assert r['stage']=='ppo' or (r['stage']=='failed' and r['failed_stage']=='ppo')
            assert r['effective'] or r.get('forced_ppo')
            assert r['clock']==oldclock
            sources[fmt]=saved
        deadline=datetime(2026,10,24,22,30,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        clock=dict(started=oldclock['started'],deadline=deadline,
                   update_deadline=oldclock['started']+(deadline-oldclock['started'])*10/12)
        assert time.time()<clock['update_deadline']<clock['deadline']
        config=copy.deepcopy(old['config']);config['hours']=(deadline-clock['started'])/3600
        DEST.mkdir(parents=True,exist_ok=False)
        manifest,_=freeze(DEST,PARENT/'frozen/opponents',old['baseline']['path'],config)
        assert manifest['features']==schema() and manifest['rules']==old['rules']
        assert manifest['architecture']==old['architecture'] and manifest['parameters']==old['parameters']
        assert {p['sha256'] for p in manifest['opponents']}=={p['sha256'] for p in old['opponents']}
        assert manifest['baseline']['sha256']==old['baseline']['sha256']
        verify_frozen(manifest)
        write_json(DEST/'clock.json',clock)
        if (PARENT/'control').exists():shutil.copytree(PARENT/'control',DEST/'control')
        assert not list((PARENT/'phase').glob('*.pending.json'))
        lineage=dict(authorization='Resume latest legal checkpoints after accepted memory repair; extend total deadline to 2026-10-24 22:30 Asia/Shanghai.',
                     created_at=time.time(),parent=str(PARENT),parent_manifest_sha256=oldhash,
                     manifest_sha256=sha256(DEST/'manifest.json'),previous_clock=oldclock,clock=clock,
                     changed_config_keys=['hours'],checkpoints={},discarded_inflight_results={})
        for fmt,saved in sources.items():
            dest=DEST/fmt;dest.mkdir()
            for p in (PARENT/fmt).glob('*.pt'):
                if p.name!='latest.pt':shutil.copyfile(p,dest/p.name)
            shutil.copytree(PARENT/fmt/'policies/support',dest/'policies/support')
            shutil.copyfile(PARENT/fmt/'controls.json',dest/'controls.json')
            # Keep teacher/validation evidence, excluding the uncommitted collection
            # at this checkpoint's batch. Its old schedule/results stay in parent.
            prefix=f"rollout-{saved['runner']['batch']:05}-{fmt}-"
            discarded=[]
            with (dest/'jobs.jsonl').open('w') as output:
                for line in (PARENT/fmt/'jobs.jsonl').read_text().splitlines():
                    row=json.loads(line)
                    if row['id'].startswith(prefix):discarded.append(dict(id=row['id'],status=row['status']));continue
                    output.write(line+'\n')
            lineage['discarded_inflight_results'][fmt]=discarded
            migrated=copy.deepcopy(saved);r=migrated['runner']
            r['clock']=clock
            if r.get('phase')=='ppo':r['phase_deadline']=clock['update_deadline']
            migrated['manifest_sha256']=sha256(DEST/'manifest.json')
            migrated['migration_parent']=dict(checkpoint=str(PARENT/fmt/'latest.pt'),sha256=EXPECTED[fmt])
            torch.save(migrated,dest/'latest.pt');write_json(dest/'state.json',r)
            reloaded=torch.load(dest/'latest.pt',map_location='cpu',weights_only=False)
            for key in ['model','optimizer','python_rng','torch_rng','cuda_rng','features','architecture','format']:
                equal(saved[key],reloaded[key])
            expected=copy.deepcopy(saved['runner']);expected['clock']=clock
            if expected.get('phase')=='ppo':expected['phase_deadline']=clock['update_deadline']
            equal(expected,reloaded['runner'])
            lineage['checkpoints'][fmt]=dict(parent_sha256=EXPECTED[fmt],migrated_sha256=sha256(dest/'latest.pt'),version=r['version'],batch=r['batch'],effective=r['effective'],forced_ppo=r.get('forced_ppo'),counters=r['counters'])
        # Duel already passed BC: use the normal phase API, no override. All three
        # stop PPO at the same update boundary before the wrapper requests evaluation.
        request_phase(DEST,'ppo',formats=['duel'],reason='Authorized recovery: align PPO end with extended shared update budget',hours=(clock['update_deadline']-time.time())/3600)
        write_json(DEST/'migration.json',lineage)
        # Exercise the actual resume loader without collecting or taking a step.
        for fmt,saved in sources.items():
            runner=FormatExperiment(DEST/fmt,fmt,manifest,clock,lambda *_: (_ for _ in ()).throw(AssertionError('no collection in migration check')),True)
            equal(runner.model.state_dict(),saved['model']);equal(runner.optimizer.state_dict(),saved['optimizer'])
            equal(torch.get_rng_state(),saved['torch_rng'])
            equal(__import__('random').getstate(),saved['python_rng'])
            assert runner.state['version']==saved['runner']['version']
            assert runner.state['effective']==saved['runner']['effective']
            assert runner.state.get('forced_ppo')==saved['runner'].get('forced_ppo')
            assert abs(runner.update_deadline()-clock['update_deadline'])<.1
        for fmt,digest in EXPECTED.items():assert sha256(PARENT/fmt/'latest.pt')==digest
        assert sha256(PARENT/'manifest.json')==oldhash and read_json(PARENT/'clock.json')==oldclock
        print(json.dumps(dict(result='migration_and_real_resume_loader_passed',destination=str(DEST),lineage=lineage),indent=2),flush=True)

if __name__=='__main__':main()
