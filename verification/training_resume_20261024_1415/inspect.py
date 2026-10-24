import os,json,hashlib,subprocess,torch
from pathlib import Path
from learning.common import sha256,read_json
from learning.manifest import tree_hashes
old=Path('/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022')
run=old/'runs/v5_lite18h_20261024_003512'
print('NOW',subprocess.check_output(['date','-Is'],text=True))
print('PROCESSES',subprocess.check_output(['ps','-eo','pid,ppid,pgid,rss,args'],text=True))
print('MEMORY',subprocess.check_output(['free','-m'],text=True))
print('DISK',subprocess.check_output(['df','-h','.'],text=True))
print('MANIFEST_HASH',sha256(run/'manifest.json'))
manifest=read_json(run/'manifest.json');print('CONFIG',json.dumps(manifest['config']))
print('CLOCK',json.dumps(read_json(run/'clock.json')))
for folder in ['learning','lua','engine_lite','vendor/arena']:
 a=tree_hashes(old/folder);b=tree_hashes(Path.cwd()/folder)
 changed=[p for p in sorted(a.keys()|b.keys()) if a.get(p)!=b.get(p)]
 print('CHANGED',folder,changed)
for fmt in manifest['config']['formats']:
 p=run/fmt/'latest.pt';s=torch.load(p,map_location='cpu',weights_only=False)
 r=s['runner'];print('CHECKPOINT',fmt,sha256(p),json.dumps({k:r.get(k) for k in ['version','batch','stage','failed_stage','effective','phase','phase_deadline','forced_ppo','pending_train','pending_validation','counters']}))
 print('BOUND',fmt,s['manifest_sha256']==sha256(run/'manifest.json'),s['features']==manifest['features'])
 print('PHASE_HISTORY',fmt,json.dumps(r.get('phase_history')))
print('NEWSTAGE_CONFIG',Path.cwd())
