"""Authorized best-checkpoint continuation under the accepted window repair."""
import copy,json,math,random,shutil,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import torch
from learning.common import ROOT,read_json,write_json,sha256
from learning.manifest import freeze,verify_frozen,tree_hashes
from learning.export import load_model
from learning.experiment import FormatExperiment,run_lock
from learning.features import select_rules,schema
from learning.phases import request_phase
from learning.train import restore_rng

PARENT=ROOT.parent/'validation_memory_repair_20261024_1321/runs/v5_lite_resume_20261024_1420'
ORIGINAL=ROOT.parent/'validation_training_repair_20261023_194022/runs/v5_lite18h_20261024_003512'
DEST=ROOT/'runs/v5_lite_windowfix_20261024_1630'
SELECTED={
 'duel':dict(path=PARENT/'duel/best.pt',sha256='6e63648d10c88243198d7af577574b4cfbe4471a45d3e6aa0d31e7153a524ec4',version=100,evidence=ORIGINAL,reason='Retained promoted champion; v200 did not pass its champion comparison. Later trend exports are not complete resumable checkpoints.'),
 'ffa4':dict(path=PARENT/'ffa4/best.pt',sha256='8d5d8d2fcd0f42385c92309b3943d74636b66541aabc914d6c3c3603f394e92e',version=100,evidence=PARENT,reason='Most recent complete promoted-best PPO checkpoint, backed by its 12-block panel.'),
 'team2v2':dict(path=PARENT/'team2v2/latest.pt',sha256='41cda3629f2237f2b999ff0dfbab7f57ddffe250694f371c25c1f860550b8306',version=60,evidence=PARENT,reason='No promoted best exists; latest complete legal PPO checkpoint is fallback, not a claim of strongest playing strength.')}

def equal(a,b):
 if isinstance(a,torch.Tensor):assert torch.equal(a,b);return
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for key in a:equal(a[key],b[key])
 elif isinstance(a,(list,tuple)):
  assert type(a)==type(b) and len(a)==len(b)
  for x,y in zip(a,b):equal(x,y)
 else:assert a==b,(a,b)

def keep(row,batch,version):
 ident=row['id']
 if ident.startswith('rollout-'):return int(ident.split('-')[1])<batch
 if ident.startswith('val') and '-' in ident:
  tag=ident.split('-')[0][3:]
  if tag.isdigit():return int(tag)<=version
 if ident.startswith('champion') and '-' in ident:
  tag=ident.split('-')[0][8:]
  if tag.isdigit():return int(tag)<=version
 return True

def main():
 with run_lock(PARENT):
  old=read_json(PARENT/'manifest.json');oldhash=sha256(PARENT/'manifest.json');oldclock=read_json(PARENT/'clock.json')
  assert oldhash=='8ec090d7b5626a093695a5f94fb6a809f5d7bb0f252aaf49af73067cc0140569'
  for folder,hashes in old['source'].items():
   current=tree_hashes(ROOT/folder);expected=dict(hashes)
   if folder=='learning':expected['control.py']='2d79571785ab3ebd1b4299653791b78e7a3f85c3cf9338684de855a3c858d1a9'
   assert current==expected,folder
  from learning import control
  assert Path(control.__file__).resolve()==ROOT/'learning/control.py'
  select_rules(old['config']['rules_dir'])
  assert not list((PARENT/'control').glob('*.pending.json'))
  events=PARENT/'control/events.jsonl';assert not events.exists() or not events.read_text().strip()
  assert not list((PARENT/'phase').glob('*.pending.json'))
  sources={};latest_hashes={}
  for fmt,choice in SELECTED.items():
   path=choice['path'];assert sha256(path)==choice['sha256']
   model,saved=load_model(path,fmt);state=saved['runner'];assert state['version']==choice['version']
   assert not state.get('pending_train') and state['stage']=='ppo'
   assert state.get('effective') or state.get('forced_ppo')
   assert state['reward_controller']['cursor']==0
   optimizer=torch.optim.Adam(model.parameters(),lr=old['config']['learning_rate']);optimizer.load_state_dict(saved['optimizer'])
   assert len(optimizer.state)>0
   for tensor in list(model.state_dict().values())+[v for slot in optimizer.state.values() for v in slot.values() if isinstance(v,torch.Tensor)]:assert torch.isfinite(tensor).all()
   restore_rng(saved);sources[fmt]=saved;latest_hashes[fmt]=sha256(PARENT/fmt/'latest.pt')
   if fmt!='team2v2':
    comparison=read_json(choice['evidence']/fmt/'validation/v000100.json')['comparison'][fmt]
    assert comparison['blocks']==12 and comparison['missing_blocks']==0 and comparison['fault_games']==0
    assert comparison['status']!='infrastructure_error'
  deadline=datetime(2026,10,25,0,0,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
  clock=dict(started=oldclock['started'],deadline=deadline,update_deadline=oldclock['started']+(deadline-oldclock['started'])*10/12)
  assert time.time()<clock['update_deadline']<deadline
  config=copy.deepcopy(old['config']);config['hours']=(deadline-clock['started'])/3600
  DEST.mkdir(parents=True,exist_ok=False)
  manifest,_=freeze(DEST,PARENT/'frozen/opponents',old['baseline']['path'],config)
  assert manifest['rules']==old['rules'] and manifest['features']==schema()
  assert manifest['architecture']==old['architecture'] and manifest['parameters']==old['parameters']
  assert {v['sha256'] for v in manifest['opponents']}=={v['sha256'] for v in old['opponents']}
  verify_frozen(manifest);write_json(DEST/'clock.json',clock)
  lineage=dict(authorization='Stop current training, deploy accepted window fix, resume strongest recent complete usable checkpoints, extend total deadline to 2026-10-25 00:00 Asia/Shanghai.',
    parent=str(PARENT),parent_manifest_sha256=oldhash,manifest_sha256=sha256(DEST/'manifest.json'),source_commit='cccf6fec2c97a5a93ad016c9bb7e8e28d371ff05',created_at=time.time(),previous_clock=oldclock,clock=clock,changed_config_keys=['hours'],checkpoints={})
  for fmt,saved in sources.items():
   choice=SELECTED[fmt];dest=DEST/fmt;dest.mkdir();state=copy.deepcopy(saved['runner'])
   state['clock']=clock
   if state.get('phase')=='ppo':state['phase_deadline']=clock['update_deadline']
   migrated=copy.deepcopy(saved);migrated['runner']=state;migrated['manifest_sha256']=sha256(DEST/'manifest.json')
   migrated['migration_parent']=dict(path=str(choice['path']),sha256=choice['sha256'],reason=choice['reason'])
   torch.save(migrated,dest/'latest.pt');write_json(dest/'state.json',state)
   (DEST/'control').mkdir(exist_ok=True);write_json(DEST/'control'/f'{fmt}.json',state['reward_controller'])
   for filename in ['last_bc.pt']:
    src=PARENT/fmt/filename
    if src.exists():shutil.copyfile(src,dest/filename)
   shutil.copyfile(choice['path'],dest/'last_ppo.pt')
   if fmt!='team2v2':
    shutil.copyfile(choice['path'],dest/'best.pt');shutil.copyfile(choice['path'],dest/'best_ppo.pt')
   shutil.copytree(PARENT/fmt/'policies/support',dest/'policies/support')
   shutil.copyfile(PARENT/fmt/'controls.json',dest/'controls.json')
   gate=next((p for p in [PARENT/fmt/'bc_gate.json',ORIGINAL/fmt/'bc_gate.json'] if p.exists()),None)
   if gate:shutil.copyfile(gate,dest/'bc_gate.json')
   kept=discarded=0
   with (dest/'jobs.jsonl').open('w') as output:
    for line in (PARENT/fmt/'jobs.jsonl').read_text().splitlines():
     row=json.loads(line)
     if keep(row,state['batch'],state['version']):output.write(line+'\n');kept+=1
     else:discarded+=1
   if state.get('pending_validation'):
    assert state['pending_validation']=='ppo'
    schedule=choice['evidence']/fmt/'schedules'/f"validation-{state['version']:06}.json"
    jobs=read_json(schedule);ids={json.loads(s)['id'] for s in (dest/'jobs.jsonl').read_text().splitlines()}
    assert all(j['id'] in ids for j in jobs)
    (dest/'schedules').mkdir();shutil.copyfile(schedule,dest/'schedules'/schedule.name)
   lineage['checkpoints'][fmt]=dict(source=str(choice['path']),source_sha256=choice['sha256'],reason=choice['reason'],version=state['version'],batch=state['batch'],effective=state['effective'],forced_ppo=state.get('forced_ppo'),counters=state['counters'],parent_latest_version=read_json(PARENT/fmt/'state.json')['version'],parent_latest_sha256=latest_hashes[fmt],kept_job_results=kept,excluded_future_results=discarded,pending_validation=state.get('pending_validation'))
  # Normal PPO phase for qualified duel; existing explicit FF4/2v2 overrides stay.
  request_phase(DEST,'ppo',formats=['duel'],reason='Authorized best-checkpoint continuation with fixed reward windows and midnight deadline',hours=(clock['update_deadline']-time.time())/3600)
  for fmt,saved in sources.items():
   def no_collection(*_):raise AssertionError('preflight must reuse completed validation evidence, not collect games')
   runner=FormatExperiment(DEST/fmt,fmt,manifest,clock,no_collection,True)
   if runner.state.get('pending_validation'):runner.validate_model('ppo')
   equal(runner.model.state_dict(),saved['model']);equal(runner.optimizer.state_dict(),saved['optimizer'])
   equal(torch.get_rng_state(),saved['torch_rng']);equal(random.getstate(),saved['python_rng'])
   assert runner.state['version']==saved['runner']['version'] and runner.state['effective']==saved['runner']['effective']
   assert runner.state.get('forced_ppo')==saved['runner'].get('forced_ppo')
   assert not runner.state.get('pending_train') and not runner.state.get('pending_validation')
   assert abs(runner.update_deadline()-clock['update_deadline'])<.1
   lineage['checkpoints'][fmt]['ready_sha256']=sha256(DEST/fmt/'latest.pt')
   lineage['checkpoints'][fmt]['completed_validation_replayed']=saved['runner'].get('pending_validation')=='ppo'
  for fmt,choice in SELECTED.items():
   assert sha256(choice['path'])==choice['sha256'] and sha256(PARENT/fmt/'latest.pt')==latest_hashes[fmt]
  assert sha256(PARENT/'manifest.json')==oldhash and read_json(PARENT/'clock.json')==oldclock
  write_json(DEST/'migration.json',lineage)
  print(json.dumps(dict(result='best-checkpoint migration and resume preflight passed',destination=str(DEST),lineage=lineage),indent=2),flush=True)

if __name__=='__main__':main()
