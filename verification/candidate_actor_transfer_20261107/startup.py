"""Initialize and reopen a B-only duel child without running its collector."""
import argparse
import json
from pathlib import Path

import torch

from learning.common import read_json, sha256
from learning.coordinator import Experiment
from learning.experiment import FormatExperiment, default_config
from learning.features import schema
from learning.model import Policy
from learning.rules_catalog import resolve_dir

PARENT_MANIFEST = '6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88'
ACTOR_CHECKPOINT = '05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab'
SEED = 202611060


def collector(*args, **kwargs):
    raise AssertionError('startup probe must not enter collection')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('child', type=Path)
    args = parser.parse_args()
    parent = args.parent.resolve()
    source = parent / 'duel/last_bc.pt'
    assert sha256(parent / 'manifest.json') == PARENT_MANIFEST
    assert sha256(source) == ACTOR_CHECKPOINT
    original = torch.load(source, map_location='cpu', weights_only=False)
    config = default_config('cpu', engine='lite') | dict(
        formats=['duel'], phase='bc', branch_weights_only=True, branch_checkpoint='last_bc',
        allow_approximate=True, rules_dir=str(resolve_dir()), human_data=str(args.child / 'empty-human'),
        seed=SEED, trainer_threads=1)
    experiment = Experiment(args.child, config=config, branch_from=parent)
    directory = experiment.directory / 'duel'
    runner = FormatExperiment(directory, 'duel', experiment.manifest, experiment.clock, collector, branch=True)
    current = runner.model.state_dict()
    assert all(torch.equal(tensor, current[key]) for key, tensor in original['model'].items() if not key.startswith('value.'))
    seeded = Policy('duel')
    torch.manual_seed(SEED)
    for layer in seeded.value.modules():
        if isinstance(layer, torch.nn.Linear):
            layer.reset_parameters()
    assert all(torch.equal(tensor, current[key]) for key, tensor in seeded.state_dict().items() if key.startswith('value.'))
    assert any(not torch.equal(tensor, current[key]) for key, tensor in original['model'].items() if key.startswith('value.'))
    assert runner.optimizer.state_dict()['state'] == {}
    assert runner.state['stage'] == 'calibration' and not runner.state['effective']
    assert all(not runner.state[key] for key in ('teacher_shards', 'dagger_shards', 'policy_shards', 'history', 'snapshots'))
    assert runner.state['counters']['optimizer_steps'] == 0
    assert not (directory / 'last_bc.pt').exists()
    assert sha256(source) == ACTOR_CHECKPOINT
    saved = torch.load(directory / 'latest.pt', map_location='cpu', weights_only=False)
    assert saved['features'] == schema()
    lineage = read_json(experiment.directory / 'branch.json')
    assert lineage['checkpoints']['duel']['sha256'] == ACTOR_CHECKPOINT
    resumed = FormatExperiment(directory, 'duel', experiment.manifest, experiment.clock, collector, resume=True)
    assert all(torch.equal(tensor, resumed.model.state_dict()[key]) for key, tensor in current.items())
    print(json.dumps(dict(source_checkpoint_sha256=ACTOR_CHECKPOINT, parent_manifest_sha256=PARENT_MANIFEST,
                          old_candidates=original['features']['candidate_selection']['version'],
                          child_candidates=saved['features']['candidate_selection']['version'],
                          seed=SEED, actor_equal=True, seeded_critic=True, optimizer_empty=True,
                          corpus_empty=True, stage=runner.state['stage'], resume_equal=True)))


if __name__ == '__main__':
    main()
