"""Read the completed BC and PPO handoffs of the failed strict run."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import runpy
import sys

import torch

from learning.common import read_json, sha256
from learning.experiment import bc_effective
from learning.formats import FORMATS
from learning.selection import validate_frozen_selection


def inspect(root):
    checks = runpy.run_path(str(Path(__file__).resolve().parents[1]/'bounded_loop_evidence_20261104/audit.py'))
    run, observed = root/'runs/bounded_loop', root/'verification/bounded_loop_observed'
    assert read_json(observed/'result.json')['reason'] == 'final evaluation panel incomplete or failed'
    manifest = sha256(run/'manifest.json')
    events = checks['lines'](run/'scheduler.jsonl')
    results = {}
    for fmt in FORMATS:
        directory = run/fmt
        rows = defaultdict(list)
        for row in checks['lines'](directory/'jobs.jsonl'):
            rows[row['id']].append(row)
        counts = Counter((e['event'],e['id']) for e in events if e.get('format')==fmt and 'id' in e)
        previous = None
        boundaries = {}
        for phase in ('bc','ppo_first','ppo_resume'):
            path = observed/'checkpoints'/phase/(fmt+'.pt')
            checkpoint = torch.load(path, map_location='cpu', weights_only=False)
            state = checkpoint['runner']
            assert checkpoint['manifest_sha256'] == manifest
            assert json.loads(json.dumps(state)) == read_json(observed/(phase+'.json'))['states'][fmt]
            assert not any(state.get(k) for k in ('pending_train','pending_validation','error','forced_ppo'))
            record = dict(sha256=sha256(path), batch=state['batch'], version=state['version'])
            if previous is None:
                assert state['stage']=='bc_complete' and state['effective'] and bc_effective(read_json(directory/'bc_gate.json'))
                record['optimizer_updates'] = sum(h['updates'] for h in state['history'] if h['method']=='bc')
                assert state['counters']['optimizer_steps'] == record['optimizer_updates'] > 0
            else:
                assert state['stage'] == 'ppo_complete'
                record.update(checks['rollouts'](directory, previous['runner'], state, rows, counts))
                assert not checks['weights_equal'](previous['model'], checkpoint['model'])
            boundaries[phase] = record
            previous = checkpoint
        assert set(boundaries['ppo_first']['jobs']).isdisjoint(boundaries['ppo_resume']['jobs'])
        selected = directory/'selected.pt'
        selection = validate_frozen_selection(directory/'selection.json', sha256(selected))
        assert selection['frozen_before_holdout'] and sha256(directory/'last_ppo.pt') == selection['selected_sha256']
        assert read_json(directory/'report/summary.json')['checkpoint_sha256'] == selection['selected_sha256']
        payload = torch.load(selected, map_location='cpu', weights_only=False)
        assert payload['manifest_sha256']==manifest and checks['weights_equal'](previous['model'], payload['model'])
        results[fmt] = dict(boundaries=boundaries, selected_sha256=selection['selected_sha256'])
    return dict(manifest_sha256=manifest, formats=results)


if __name__ == '__main__':
    print(json.dumps(inspect(Path(sys.argv[1]).resolve()), indent=2))
