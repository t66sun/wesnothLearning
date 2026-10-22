"""Real-runtime integration; intentionally separate from fast unit tests."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import gzip
import json
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import addons
import native
from match import play_game


def main():
    p=argparse.ArgumentParser();p.add_argument('--wesnoth');p.add_argument('--output',default='smoke_results')
    args=p.parse_args();exe=native.find_wesnoth(args.wesnoth)
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='arena-fixtures-') as temp:
        cases={
            'ErrorEval': "local M={}\nfunction M:evaluation() error('fixture evaluation') end\nfunction M:execution() end\nreturn M",
            'ErrorExec': "local M={}\nfunction M:evaluation() return 100000 end\nfunction M:execution() error('fixture execution') end\nreturn M",
            'Illegal': "local M={}\nfunction M:evaluation() return 100000 end\nfunction M:execution() ai.recruit('Spearman', {1,1}) end\nreturn M",
            'HangEval': "local M={}\nfunction M:evaluation() while true do end end\nfunction M:execution() end\nreturn M",
            'HangExec': "local M={}\nfunction M:evaluation() return 100000 end\nfunction M:execution() while true do end end\nreturn M",
            'BadScore': "local M={}\nfunction M:evaluation() return 'bad' end\nfunction M:execution() end\nreturn M",
            'Syntax': 'this is not Lua',
        }
        paths={}
        for name,code in cases.items():
            path=addons.create(name,temp);(path/'lua/bot.lua').write_text(code,encoding='utf-8');paths[name]=path
        jobs=[('valid',dict(bots=[str(native.ROOT/'sdk/template_bot'),'baseline'],max_turns=30)),
              ('ffa4',dict(bots=[str(native.ROOT/'sdk/sample_bot')]*4,max_turns=2)),
              ('ffa8',dict(bots=[str(native.ROOT/'sdk/sample_bot')]*8,max_turns=2))]
        jobs += [(name,dict(bots=[str(path),str(native.ROOT/'sdk/sample_bot')],timeout=.15,first_timeout=.2,max_turns=2)) for name,path in paths.items()]
        jobs += [('lenient',dict(bots=[str(paths['ErrorEval']),str(native.ROOT/'sdk/sample_bot')],lenient=True,max_turns=2))]
        jobs += [('ffa_fault',dict(bots=[str(paths['ErrorEval'])]+[str(native.ROOT/'sdk/sample_bot')]*3,max_turns=2))]
        def run(item):
            name,kwargs=item
            result=play_game(**kwargs,wesnoth=exe,replay_path=out/f'{name}.json')
            if name in paths:
                assert 1 in result['faults'],(name,result)
                assert result['winner']==2,(name,result)
            elif name=='lenient':
                assert result['winner']==0 and result['lenient'] and result['faults']
            elif name=='ffa_fault':
                assert result['rank_points'][1]==0 and len(result['survivors'])==3
            else:
                assert not result['faults'],(name,result)
                assert result['native_replay'],(name,'missing native replay')
                replay=gzip.decompress(Path(result['native_replay']).read_bytes()).decode('utf-8')
                assert '[replay]' in replay and '[replay_start]' in replay
            return name,result
        with ThreadPoolExecutor(max_workers=4) as pool: results=dict(pool.map(run,jobs))
        (out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print('PASS:',len(results),'native integration cases')


if __name__=='__main__': main()
