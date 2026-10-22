"""Benchmark worker lifecycle regressions independent of a native install."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from learning import benchmark_runner
from learning.benchmark import COMPONENTS


class FakeAdapter:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.observed = self.legal = self.executed = self.stepped = 0
        self.closed = False

    def observe(self, side):
        self.events.append('observe')
        self.observed += 1
        return {'current_side': side, 'turn': 1, 'finished': False}

    def legal_actions(self, side):
        self.events.append('legal')
        self.legal += 1
        return []

    def execute_candidate(self, action):
        self.events.append('execute')
        self.executed += 1
        return {'committed': True, 'view': {'current_side': 2, 'turn': 1, 'finished': False}}

    def step(self, action):
        self.events.append('execute')
        self.stepped += 1
        return {'current_side': 2, 'turn': 1, 'finished': False}

    def close(self):
        self.closed = True


class BenchmarkWorkerTests(unittest.TestCase):
    def test_hot_equal_work_emits_begin_after_warmup(self):
        events = []
        adapter = FakeAdapter(events)
        emitted = []

        def emit(kind, value):
            events.append(kind)
            emitted.append((kind, value))

        work = dict(cache='hot', mode='equal_work', format='duel', script_turns=1,
                    density='regular', seed=1, factions_rotation=0, seat=1,
                    turn_limit=10)
        config = dict(engine='lite', work=work, executable='unused', rules_dir='unused',
                      timeout=5, max_decisions=4, script_turns=1)
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, 'rules.json').write_text('{}', encoding='utf-8')
            config['rules_dir'] = temporary
            with mock.patch.object(benchmark_runner, 'make_spec', return_value={}), \
                    mock.patch.object(benchmark_runner, '_cpu', return_value=0.0), \
                    mock.patch.object(benchmark_runner, '_emit', side_effect=emit), \
                    mock.patch('learning.adapters.LiteAdapter', return_value=adapter):
                benchmark_runner.worker(config)

        self.assertEqual(events[0:3], ['observe', 'legal', 'BEGIN'])
        self.assertEqual(events[-1], 'RESULT')
        result = emitted[-1][1]
        self.assertEqual(result['actions'], 2)
        self.assertEqual(result['terminal_reason'], 'script_complete')
        self.assertEqual(adapter.stepped, 2)
        self.assertEqual(adapter.executed, 0)
        self.assertTrue(adapter.closed)

    def test_main_writes_acceptance_for_runner_manifest(self):
        def measured(engine, work, **kwargs):
            native = engine == 'native'
            return dict(host_id='test-host', cpu_quota=1.0, workers=1, inference='cpu', threads=1,
                        wall_seconds=10.0 if native else 1.0,
                        cpu_core_seconds=10.0 if native else 1.0,
                        peak_rss_bytes=20.0 if native else 10.0,
                        peak_pss_bytes=20.0 if native else 10.0,
                        disk_bytes=0.0, startup_seconds=0.0, faults=[],
                        cpu_scope='process_tree_including_coordinator',
                        actions=1, turns=1, terminal_reason='script_complete',
                        cache_aligned=True, work_signature='script',
                        components_seconds={name: 0.0 for name in COMPONENTS})

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'out'
            argv = ['benchmark_runner', '--executable', 'wesnoth', '--rules-dir', temporary,
                    '--output', str(output), '--formats', 'duel', '--caches', 'cold', 'hot',
                    '--modes', 'equal_work', '--densities', 'regular', '--blocks', '30',
                    '--seats', '1', '2', '--max-decisions', '1']
            artifacts = {name: dict(path=name, sha256='0' * 64)
                         for name in ('native_executable', 'lite_rules', 'astra')}
            with mock.patch.object(benchmark_runner.sys, 'argv', argv), \
                    mock.patch.object(benchmark_runner.sys, 'platform', 'linux'), \
                    mock.patch.object(benchmark_runner, 'freeze_artifacts', return_value=artifacts), \
                    mock.patch.object(benchmark_runner, 'measure', side_effect=measured):
                benchmark_runner.main()
            report = json.loads((output / 'acceptance.json').read_text(encoding='utf-8'))

        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['artifacts_frozen'])
        self.assertEqual({group['status'] for group in report['groups']}, {'passed'})


if __name__ == '__main__':
    unittest.main()
