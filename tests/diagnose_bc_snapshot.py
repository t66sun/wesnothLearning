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
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    intent = data['intent']
    for variant in ('baseline', 'work', 'probes', 'positions', 'rated', 'combat_order', 'all_search'):
        modules = host_modules()
        source = traced(modules['candidates.lua'])
        key = dict(work='total=12000', probes='move_probes=48', positions='positions=64', rated='rated=40').get(variant)
        if key: source = source.replace(key, key.split('=')[0]+'=1000000')
        if variant == 'all_search':
            for key in ('total=12000', 'move_probes=48', 'positions=64', 'rated=40'):
                source = source.replace(key, key.split('=')[0]+'=1000000')
        if variant == 'combat_order':
            source = source.replace('if not d then return end', "if not d then return end\n                if category=='attack' then d.combat=true end")
            source = source.replace("d.category=='attack'", 'd.combat').replace("d.category~='attack'", 'not d.combat')
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
        result = dict(variant=variant, intent=intent, matched=matching(row['candidates'],intent)>=0,
                      generated=matching(pool,intent)>=0, reason=reason(row['candidates'],intent), timing=row['timing'])
        for key in ('reach','destinations','selected'):
            items = actor.get(key, [])
            result[key+'_count'] = len(items)
            result[key+'_target'] = [(i,x) for i,x in enumerate(items) if tuple((x.get('p') if isinstance(x,dict) else x)[:2])==target]
        print(json.dumps(result), flush=True)
        host.adapter.close()


if __name__ == '__main__':
    main()
