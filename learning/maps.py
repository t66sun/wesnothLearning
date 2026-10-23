"""Frozen native maps; held-out layouts never enter training or reward calibration."""
from pathlib import Path
import hashlib
import json
from .common import ROOT

SPLITS={
    'duel':dict(train=('the_freelands','weldyn_channel','sablestone_delta'),validation=('hamlets',),holdout=('caves_of_the_basilisk','ruined_passage')),
    'ffa4':dict(train=('clash','isars_cross'),validation=('loris_river',),holdout=('morituri',)),
    'team2v2':dict(train=('clash','isars_cross'),validation=('loris_river',),holdout=('morituri',)),
}


def freeze_map(source,name,output=None,catalog=None):
    """Convert a genuine native .map; the distribution inventory proves its version."""
    import re
    source=Path(source);raw=source.read_bytes();text=raw.decode('utf-8-sig')
    if not re.fullmatch(r'[a-z0-9_]+',name): raise ValueError('map name must be a lowercase slug')
    provenance=json.loads(Path(catalog or ROOT/'data/rules/1.18.8/catalog.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(raw).hexdigest()
    inventories=[entry.get('source_manifest',{}).get('files',{}) for entry in provenance.get('captures',[])]
    if provenance.get('source_version')!='1.18.8' or not any(digest in inventory.values() for inventory in inventories):
        raise ValueError('map source is absent from the frozen 1.18.8 distribution inventory')
    border=1;terrain=[];starts={}
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        if '=' in line and ',' not in line:
            key,value=line.split('=',1)
            if key.strip()=='border_size': border=int(value)
            continue
        row=[]
        for x,cell in enumerate(line.split(',')):
            match=re.fullmatch(r'\s*(?:(\d+)\s+)?([^\s,]+)\s*',cell)
            if not match: raise ValueError('invalid native map cell')
            side,code=match.groups();row.append(code)
            if side: starts[int(side)]=[x+1-border,len(terrain)+1-border]
        terrain.append(row)
    if not terrain or any(len(row)!=len(terrain[0]) for row in terrain): raise ValueError('native map must be rectangular')
    if border: terrain=[row[border:-border] for row in terrain[border:-border]]
    if not starts or sorted(starts)!=list(range(1,len(starts)+1)): raise ValueError('map needs contiguous starting positions')
    height=len(terrain);width=len(terrain[0])
    if any(not 1<=x<=width or not 1<=y<=height for x,y in starts.values()): raise ValueError('starting position outside playable map')
    data=dict(native_version='1.18.8',name=name,source_path=str(source.resolve()),source_sha256=digest,
        board=dict(width=width,height=height,terrain=terrain,starts=[starts[i] for i in sorted(starts)]))
    from .common import write_json
    path=Path(output or ROOT/'data/rules/1.18.8/maps')/(name+'.json')
    if path.exists(): raise FileExistsError(path)
    write_json(path,data);return path


def frozen_map(name):
    path=ROOT/'data/rules/1.18.8/maps'/(name+'.json')
    if not path.exists(): raise ValueError(f'missing frozen 1.18.8 map: {path}; export it before collecting')
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('native_version')!='1.18.8' or not data.get('source_sha256'):
        raise ValueError('map lacks native version/source hash: '+name)
    board=data['board']
    if len(board['terrain'])!=board['height'] or any(len(row)!=board['width'] for row in board['terrain']): raise ValueError('invalid map dimensions')
    return board,hashlib.sha256(path.read_bytes()).hexdigest()


def decorate(job,format_name,index,phase):
    if phase=='train' and index%2==0:
        from .common import VENDOR
        path=VENDOR/'maps'/f'arena{len(job["bots"])}.json'
        board=json.loads(path.read_text(encoding='utf-8'));digest=hashlib.sha256(path.read_bytes()).hexdigest();name=path.stem
    else:
        split='train' if phase=='train' else 'holdout' if phase=='final' else 'validation'
        names=SPLITS[format_name][split];name=names[(index//2 if split=='train' else index)%len(names)]
        board,digest=frozen_map(name)
    job['map_override']=board
    job.setdefault('meta',{}).update(map=name,map_sha256=digest,map_partition=phase)
    family=dict(format=format_name,map=digest,seed=job['seed'],factions=job['factions'],teams=job.get('teams'))
    job['game_family']=hashlib.sha256(json.dumps(family,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if phase=='train': job['max_turns']=60
    return job
