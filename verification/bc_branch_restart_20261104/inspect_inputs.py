"""Inspect BC initialization from the sealed item-10 corpus without running a phase."""
import gzip
import json
import sys
import tempfile
from pathlib import Path

import torch

from learning.common import ROOT, read_json, sha256
from learning.coordinator import Experiment
from learning.data import record_split
from learning.experiment import FormatExperiment, coverage_gate
from learning.rowpack import row_meta


def inspect(inventory):
    parent = Path(inventory['run'])
    manifest = read_json(parent/'manifest.json')
    config = manifest['config'] | dict(hours=.32, phase='bc', branch_reset_optimizer=True,
                                       branch_restart_bc=True, bc_games={fmt:24 for fmt in inventory['formats']})
    results = dict(parent_manifest=sha256(parent/'manifest.json'), formats={})
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        child = Experiment(Path(tmp)/'child', config=config, branch_from=parent)
        for fmt, source in inventory['formats'].items():
            runner = FormatExperiment(child.directory/fmt, fmt, child.manifest, child.clock, None, branch=True)
            expected = {f['path']:f['sha256'] for f in source['files'] if f['role'] in ('teacher','dagger')}
            assert set(runner.state['teacher_shards'] + runner.state['dagger_shards']) == set(expected)
            assert all(sha256(path) == digest for path, digest in expected.items())
            families = {'train':set(), 'validation':set()}
            for path in expected:
                with gzip.open(path, 'rt') as shard:
                    row = row_meta(shard.readline())
                assert row['source'] == 'astra' and row['teacher_profile'] == manifest['teacher']['teacher_profile']
                assert row['schema'] == manifest['row_schema'] and row['candidate_version'] == 'schema5-work-12000-v8'
                assert row['split_rule'] == 'scenario-v2' and record_split(row) == row['split']
                families[row['split']].add(row['scenario_family'])
            assert families['train'].isdisjoint(families['validation'])
            original = next(f for f in source['files'] if f['role']=='latest')
            assert sha256(original['path']) == original['sha256']
            weights = torch.load(original['path'], map_location='cpu', weights_only=False)['model']
            assert all(torch.equal(v, weights[k]) for k,v in runner.model.state_dict().items())
            state = runner.state
            assert state['stage']=='calibration' and not state['effective'] and state['batch']==state['version']==0
            assert not state['history'] and not runner.optimizer.state and state['counters']['optimizer_steps']==0
            evidence = runner.teacher_evidence()
            assert len(evidence) == len(state['teacher_shards'])
            coverage = coverage_gate(evidence)
            assert coverage == read_json(parent/fmt/'bc_gate.json')['coverage']
            results['formats'][fmt] = dict(parent_checkpoint=original['sha256'], teacher_games=len(evidence),
                dagger_shards=len(state['dagger_shards']), scenario_families={k:len(v) for k,v in families.items()},
                coverage=coverage['actions']['all'], stage=state['stage'], effective=state['effective'],
                optimizer_steps=state['counters']['optimizer_steps'])
    return results


if __name__ == '__main__':
    print(json.dumps(inspect(read_json(sys.argv[1])), indent=2))
