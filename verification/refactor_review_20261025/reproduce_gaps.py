"""Focused review diagnostics: reproducing a bug is NOT acceptance passing.

Run from the repository root with its Python environment; no engine, games,
server, or training loop. Tiny local learner calls only. All output files are
temporary. This records behavior of 642a890, not future repaired code.
"""
import json
import random
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import torch

from learning import bc, ppo
from learning.data import split, validate_record
from learning.experiment import FormatExperiment
from learning.export import export_checkpoints
from learning.updates import rollout_identity
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _bc, _records, _run
from tests.v5.test_selection import panel


def final_selection_gap():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        (directory / 'validation').mkdir()
        (directory / 'best.pt').write_bytes(b'champion100')
        (directory / 'last_ppo.pt').write_bytes(b'latest143')
        (directory / 'validation/v000100.json').write_text(json.dumps(panel(.1)), encoding='utf-8')
        runner = FormatExperiment.__new__(FormatExperiment)
        runner.directory, runner.fmt = directory, 'duel'
        runner._checkpoint_version = lambda path: {'best.pt': 100, 'last_ppo.pt': 143}[Path(path).name]
        runner.collector, runner.validate_model = Mock(), Mock()
        try:
            runner._select_final()
        except FileNotFoundError as error:
            assert Path(error.filename).name == 'v000143.json'
            assert not runner.collector.called and not runner.validate_model.called
            print('BUG_REPRODUCED V1: final selection raises FileNotFoundError v000143.json; nomination calls=0')
        else:
            raise AssertionError('V1 did not reproduce')


def export_identity_gap():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        runner = FormatExperiment.__new__(FormatExperiment)
        runner.directory, runner.fmt = directory, 'duel'
        runner.model = helpers.model()
        runner.optimizer = torch.optim.Adam(runner.model.parameters())
        runner.config = dict(seed=1, bc_records=8, epochs=1, minibatch=2, validation_interval=10)
        runner.clock = dict(started=time.time())
        runner.controller = Mock()
        runner.controller.freeze.return_value = {}
        runner.human_paths = lambda: []
        runner.update_deadline = lambda: float('inf')
        runner.save = Mock()
        runner.state = dict(pending_train=dict(method='ppo', paths=['rollout'], cursor=None,
                                              reward_config=dict(entropy=.01, bc_aux=.1)),
                            teacher_shards=[], dagger_shards=[], version=0, batch=0, history=[],
                            families_seen=[], counters=dict(optimizer_steps=0, decisions_seen=0,
                                                            unique_families_seen=0, effective_dataset_passes=0.))
        with patch('learning.experiment.read_shards', return_value=[]), \
                patch('learning.experiment.train', return_value=dict(interrupted=False, updates=1,
                                                                     committed_decisions=4)):
            runner.finish_train()
        path = directory / 'last_ppo.pt'
        state = torch.load(path, weights_only=False)
        keys = ('engine', 'engine_version', 'rng_version', 'combat_version',
                'teacher', 'teacher_profile', 'teacher_source_sha256')
        assert all(key not in state for key in keys)
        # Export rejects the actual first-format checkpoint before other formats
        # are reached; no large Lua package or numeric export is generated.
        try:
            export_checkpoints(dict.fromkeys(('duel', 'ffa4', 'team2v2'), path), directory / 'export')
        except ValueError as error:
            assert 'checkpoint lacks combat or teacher profile identity' in str(error)
            print('BUG_REPRODUCED V2:', str(error))
        else:
            raise AssertionError('V2 did not reproduce')


def resumed_counter_gap():
    records = _records([('b', 2, 0.), ('c', 3, 0.), ('d', 4, 0.), ('e', 2, 0.)])
    model, optimizer, first = _run(records, epochs=1)
    progress = dict(first['cursor'], loss_sum=first['loss'] * first['updates'], updates=first['updates'],
                    decisions_seen=first['decisions_seen'], committed_decisions=first['committed_decisions'],
                    inspected_decisions=first['inspected_decisions'])
    second = ppo.update(model, optimizer, records, bc_records=_bc(), epochs=2,
                        minibatch=2, progress=progress, plan_seed=5)
    assert first['committed_decisions'] == 11
    assert second['decisions_seen'] == 22 and second['committed_decisions'] == 11
    print('BUG_REPRODUCED V3: resumed updates=%s decisions_seen=%s committed_decisions=%s; finish_train adds only committed'
          % (second['updates'], second['decisions_seen'], second['committed_decisions']))


def bc_rng_gap():
    records = helpers.sequence_rows(turns=1, decisions_per_turn=2, game_family='family-1')
    for row in records:
        row['split'] = split(row['game_family'])
    model = helpers.model(seed=73)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    random.seed(125)
    before = random.getstate()
    weights = {key: value.detach().clone() for key, value in model.state_dict().items()}
    with patch('learning.bc.time.time', side_effect=[0., 2.]):
        result = bc.update(model, optimizer, records, epochs=1, deadline=1.)
    assert result['interrupted'] and result['updates'] == 0
    assert all(torch.equal(weights[key], value) for key, value in model.state_dict().items())
    assert before != random.getstate()
    print('BUG_REPRODUCED V4: BC cancellation updates=0 weights unchanged, but Python sampling RNG advanced')


def rollout_identity_gap():
    row = dict(game_id='game-A', side=1, turn=1, decision=0, version=7, engine_id='lite-0.2',
               rules_version='rule', rng_version='deterministic-expected_damage_v1',
               combat_version='expected_damage_v1', teacher_profile='expected_damage_v1',
               reward_version=0, reward_formula_id='reward', game_family='family',
               choice=0, log_probability=-.1, reward=1.)
    other = dict(row, game_id='game-B', side=2, turn=9, decision=99,
                 choice=1, log_probability=-4., reward=-1.)
    assert rollout_identity([row]) == rollout_identity([other])
    print('BUG_REPRODUCED V5: different game/side/turn/decision/choice/old_logp/reward produce the same rollout identity')


def native_teacher_gap():
    row = helpers.synthetic_decision_row()
    validate_record(row)
    row.update(engine_id='native-1.18.8', rng_version='native-1.18.8', combat_version='native-1.18.8')
    row.pop('teacher_profile', None)
    try:
        validate_record(row)
    except ValueError as error:
        assert 'different Astra teacher profile' in str(error)
        print('BUG_REPRODUCED V6: native Astra row rejected by deterministic-lite teacher profile check')
    else:
        raise AssertionError('V6 did not reproduce')


if __name__ == '__main__':
    torch.set_num_threads(1)
    for diagnostic in (final_selection_gap, export_identity_gap, resumed_counter_gap,
                       bc_rng_gap, rollout_identity_gap, native_teacher_gap):
        diagnostic()
    print('DIAGNOSTICS_COMPLETE: six acceptance gaps reproduced; NOT an acceptance pass')
