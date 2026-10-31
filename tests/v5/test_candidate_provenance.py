"""Candidate-version provenance: current generated pools and captures without timing.

``learning/lite_host.py`` derives ``candidate_version`` from the decision
timing: ``schema5-`` plus ``timing.budget`` when the host generated a real
candidate pool, else the frozen ``fixed-20000-v1`` default.  Astra seats the
job does not collect take the stub path (no ``budget`` key), so their
derivation uses the legacy fallback even though only learner seats reach the shard.  Human
captures carry whatever the replay observer recorded: an old capture without
timing imports as v1, a capture with the v3 budget as v3.
"""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest import mock

import torch

from learning import features
from learning.features import schema
from learning.human import OBSERVER_VERSION, PREFIX, import_capture
from learning.lite_host import LiteHost, play_lite_job
from learning.model import ARCHITECTURE, Policy
from tests.test_core import record
from tests.v5 import helpers
from tests.v5.test_pipeline_contract import catalog_patch, frozen_rules, read_gzip


def _version(timing):
    """The provenance expression from learning/lite_host.py, applied to a DTO."""
    return 'schema5-' + timing.get('budget', 'fixed-20000-v1')


def _spy(calls):
    original = LiteHost.decision

    def spy(host, side, **kwargs):
        result = original(host, side, **kwargs)
        calls.append(dict(side=side, teacher=kwargs.get('teacher', False),
                          generate_candidates=kwargs.get('generate_candidates', True),
                          timing=dict(result['timing'])))
        return result
    return spy


def _capture(directory, name, timing=None):
    sample = record()
    sample.pop('candidate_version')
    sample.update(source='human', teacher=False, format='duel',
                  actual=dict(kind='end_turn'), action_index=0, human_control=True)
    sample['candidates'][sample['choice']]['kind'] = 'end_turn'
    if timing is not None:
        sample['timing'] = timing
    events = [dict(event='sample', record=sample),
              dict(event='complete', source_sha256='fixture',
                   observer_version=OBSERVER_VERSION, expected_actions=1)]
    path = Path(directory) / name
    path.write_text('Battle for Wesnoth v1.18.8\n'
                    + '\n'.join(PREFIX + json.dumps(event) for event in events) + '\n')
    return path, dict(category='standard_multiplayer', era='era_default', format='duel',
                      game_id='game_0001', family_id='g', curated_sha256='fixture')


class CandidateProvenanceTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.rules_dir = frozen_rules(self.directory / 'rules')

    def frozen_addon(self, format_name='duel'):
        """A real exported addon; FrozenPolicies loads model.pt beside the addon dir."""
        torch.manual_seed(173)
        torch.set_num_threads(1)
        addon = self.directory / 'Student'
        (addon / 'lua').mkdir(parents=True, exist_ok=True)
        (addon / 'lua' / 'config.lua').write_text('return {["mode"]="sample"}', encoding='utf-8')
        model = Policy(format_name).eval()
        with catalog_patch(self.rules_dir):
            checkpoint = dict(model=model.state_dict(), architecture=ARCHITECTURE,
                              features=schema(), format=format_name)
        torch.save(checkpoint, self.directory / 'model.pt')
        return addon

    def job(self, **overrides):
        value = dict(id='provenance-job', seed=7, bots=[self.frozen_addon(), 'astra'],
                     game_spec=helpers.spec(max_turns=4),
                     rules_dir=str(self.rules_dir),
                     shard=str(self.directory / 'shards' / 'provenance.jsonl.gz'),
                     deadline=time.time() + 120, max_decisions=1000,
                     meta=dict(format='duel', map='synthetic', map_sha256='sha-a',
                               map_partition='train', context='solo'),
                     teams=[1, 2], factions=['Fighter', 'Skeleton'],
                     game_family='family-1',
                     learning=dict(sides={'1': {}}, version='v5-test'),
                     bootstrap_policy=lambda row: 0.0)
        value.update(overrides)
        return value

    def test_unrecorded_teacher_uses_fallback_and_collected_rows_are_v5(self):
        job = self.job()
        calls = []
        with mock.patch.object(LiteHost, 'decision', _spy(calls)):
            with catalog_patch(self.rules_dir):
                outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        rows = read_gzip(job['shard'])
        self.assertTrue(rows)
        self.assertEqual({row['side'] for row in rows}, {1})
        self.assertEqual({row['candidate_version'] for row in rows},
                         {'schema5-work-12000-v5'})
        diagnostic = [call for call in calls if not call['teacher'] and not call['generate_candidates']]
        collected = [call for call in calls if call['side'] == 1 and call['generate_candidates']]
        unrecorded = [call for call in calls if call['teacher']]
        self.assertTrue(collected, calls)
        self.assertTrue(unrecorded, calls)
        self.assertTrue(diagnostic, calls)
        self.assertEqual(len(calls), len(collected)+len(unrecorded)+len(diagnostic))
        self.assertTrue(all(call['side']==1 and 'budget' not in call['timing'] for call in diagnostic))
        self.assertTrue(all('metric_event' not in row for row in rows))
        for call in unrecorded:
            self.assertTrue(call['teacher'], call)
            self.assertFalse(call['generate_candidates'], call)
            self.assertNotIn('budget', call['timing'], call)
            self.assertEqual(_version(call['timing']), 'schema5-fixed-20000-v1')
        for call in collected:
            self.assertFalse(call['teacher'], call)
            self.assertTrue(call['generate_candidates'], call)
            self.assertEqual(call['timing']['budget'], 'work-12000-v5', call)
            self.assertEqual(_version(call['timing']), 'schema5-work-12000-v5')

    def test_human_capture_without_timing_keeps_v1_and_validates(self):
        path, row = _capture(self.directory, 'capture-v1.log')
        rows, coverage = import_capture(path, row)
        self.assertEqual(rows[0]['candidate_version'], 'schema5-fixed-20000-v1')
        helpers.validate(rows[0], 'duel')
        self.assertEqual(coverage['end_turn']['matched'], 1)

    def test_human_capture_with_v3_budget_imports_as_v3(self):
        path, row = _capture(self.directory, 'capture-v3.log',
                             timing={'budget': 'fixed-20000-v3', 'truncated': False,
                                     'ms': 4, 'predictions': 0, 'work': 7})
        rows, _ = import_capture(path, row)
        self.assertEqual(rows[0]['candidate_version'], 'schema5-fixed-20000-v3')
        helpers.validate(rows[0], 'duel')


if __name__ == '__main__':
    unittest.main()
