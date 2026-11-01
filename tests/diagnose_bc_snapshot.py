"""Manual candidate-stage ablations on a recorded referee snapshot."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from diagnose_bc_coverage import traced
from learning.coverage import matching, reason
from learning.lite_host import LiteHost, host_modules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--source-tree',type=Path,required=True,
                        help='frozen work-12000-v7 source tree for these ablations')
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    intent = data['intent']
    for variant in ('baseline', 'work', 'probes', 'positions', 'rated', 'combat_order', 'safe_shortlist', 'all_search'):
        modules = host_modules()
        for name in ('candidates.lua','candidate_selection.lua'):
            modules[name] = (args.source_tree/'lua'/name).read_text()
        source = traced(modules['candidates.lua'])
        key = dict(work='total=12000', probes='move_probes=48', positions='positions=64', rated='rated=40').get(variant)
        if key: source = source.replace(key, key.split('=')[0]+'=1000000')
        if variant == 'all_search':
            for key in ('total=12000', 'move_probes=48', 'positions=64', 'rated=40'):
                source = source.replace(key, key.split('=')[0]+'=1000000')
        if variant == 'combat_order':
            source = source.replace('if not d then return end', "if not d then return end\n                if category=='attack' then d.combat=true end")
            source = source.replace("d.category=='attack'", 'd.combat').replace("d.category~='attack'", 'not d.combat')
        if variant == 'safe_shortlist':
            source = source.replace('scored[#scored+1]={p=p,score=score}',
                "scored[#scored+1]={p=p,score=score,threats=#(threats[p[1]..','..p[2]] or {})}")
            source = source.replace('for i=1,math.min(#scored,WORK.positions) do destinations[i]=scored[i] end', '''local safe={}
            for _,d in ipairs(scored) do safe[#safe+1]=d end
            table.sort(safe,function(a,b)
                if a.threats~=b.threats then return a.threats<b.threats end
                if a.score~=b.score then return a.score>b.score end
                return a.p[1]<b.p[1] or a.p[1]==b.p[1] and a.p[2]<b.p[2]
            end)
            local chosen={}
            for i=1,#scored do
                for _,d in ipairs {scored[i],safe[i]} do
                    if not chosen[d] and #destinations<WORK.positions then
                        destinations[#destinations+1]=d;chosen[d]=true
                    end
                end
                if #destinations>=WORK.positions then break end
            end''')
            start = source.index('    table.sort(destinations,function(a,b)')
            end = source.index('    for i=1,math.min(WORK.rated',start)
            source = source[:start]+source[end:]
        source = source.replace('local reachable={}',
            'trace.actors[#trace.actors].destinations=destinations;trace.actors[#trace.actors].selected=selected;trace.actors[#trace.actors].reach=reach\n            local reachable={}')
        modules['candidates.lua'] = source
        with patch('learning.lite_host.host_modules', return_value=modules):
            host = LiteHost(data['spec'])
        host.restore(data['snapshot'])
        row = host.decision(data['side'])
        trace = row['timing'].pop('trace')
        pool = trace.pop('pool', [])
        actor = next((a for a in trace['actors'] if (a['x'],a['y']) == (intent.get('x'),intent.get('y'))), {})
        target = (intent.get('tx'),intent.get('ty'))
        matched = matching(row['candidates'],intent)>=0
        result = dict(variant=variant, source_tree=str(args.source_tree), intent=intent, matched=matched,
                      generated=matching(pool,intent)>=0, reason=None if matched else reason(row['candidates'],intent), timing=row['timing'])
        for key in ('reach','destinations','selected'):
            items = actor.get(key, [])
            result[key+'_count'] = len(items)
            result[key+'_target'] = [(i,x) for i,x in enumerate(items) if tuple((x.get('p') if isinstance(x,dict) else x)[:2])==target]
        print(json.dumps(result), flush=True)
        host.adapter.close()


if __name__ == '__main__':
    main()
