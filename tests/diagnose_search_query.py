"""Native referee audit of independent teacher queries; no policy receives audit state."""
import argparse
import json
from pathlib import Path
import shutil
import time

from learning.common import ROOT, sha256, write_json
import match
import native


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wesnoth',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    terrain=[['Gg']*15 for _ in range(15)]
    for x,y in ((2,2),(14,14)): terrain[y-1][x-1]='Kh'
    for x,y in ((2,3),(3,2),(13,14),(14,13)): terrain[y-1][x-1]='Ch'
    cases=[('control','beam',0,False),('beam','beam',3,False),('pvs','pvs',3,False),
           ('uct','uct',3,False),('hidden','beam',3,True)]
    traces={};results={}
    for name,algorithm,queries,hidden in cases:
        folder=output/name;addon=folder/'search_teacher'
        shutil.copytree(ROOT/'learning/teachers/search_teacher',addon)
        (addon/'lua/bot.lua').rename(addon/'lua/implementation.lua')
        shutil.copyfile(ROOT/'tests/fixtures/search_query_audit.lua',addon/'lua/bot.lua')
        config=dict(algorithm=algorithm,depth=2,width=3,root_width=6,reply_width=2,
                    tactical_ms=700,planning_ms=1000,cache_combat=True,outside_keep_gold=.1,
                    tree_depth=3,mc_iterations=12,mc_depth=3,mc_width=3,search_seed=9187)
        (addon/'lua/config.lua').write_text('return '+native.lua(config),encoding='utf-8')
        (addon/'lua/audit_options.lua').write_text('return '+native.lua(dict(queries=queries,hidden_variant=hidden)),encoding='utf-8')
        replay=folder/'audit.json'
        results[name]=match.play_game([str(addon),'baseline'],seed=713,factions=['Loyalists','Northerners'],
            max_turns=1,wesnoth=args.wesnoth,replay_path=replay,experiment_deadline=time.time()+120,
            timeout=2,first_timeout=20,fog=True,shroud=True,
            map_override=dict(width=15,height=15,terrain=terrain,starts=[[2,2],[14,14]]))
        events=[json.loads(line) for line in replay.with_suffix('.events.jsonl').read_text().splitlines()]
        rows=[row['data'] for row in events if row['event']=='SEARCH_QUERY_AUDIT']
        assert not results[name]['faults'],results[name]
        assert len(rows)==1,(name,rows)
        traces[name]=rows[0]
    for name in ('beam','pvs','uct'):
        for field in ('draws','successor_id','successor_underlying','public'):
            assert traces[name].get(field)==traces['control'].get(field),(name,field)
    assert traces['hidden']['public']==traces['beam']['public'],'hidden information changed public input'
    assert traces['hidden']['plan']==traces['beam']['plan'],'hidden information changed decision'
    summary=dict(source=args.source,native_executable_sha256=sha256(args.wesnoth),
                 entropy_sha256=sha256(match.ENTROPY_SHIM),results=results,traces=traces,passed=True)
    write_json(output/'summary.json',summary)
    print(json.dumps(dict(passed=True,cases=list(traces),source=args.source)),flush=True)


if __name__=='__main__':
    main()
