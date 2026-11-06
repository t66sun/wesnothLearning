"""Semantic accounting assertions; real-input checks run inside probe.py."""
import ast
from pathlib import Path
import unittest

from census import intervals, ledger, union_seconds


class AccountingTests(unittest.TestCase):
    def test_rejected_step_is_not_a_never_attempted_step(self):
        entry = dict(method='ppo', batch=1, planned_steps=12, committed_steps=4,
                     kl_stopped=True, inspected_decisions=869, committed_decisions=716,
                     eligible_decisions=447, unique_families_seen=4, sequence_windows=10,
                     approx_kl=.03, elapsed_hours=2., cursor={})
        result = ledger([entry])[0]
        self.assertEqual(result['rejected_steps'], 1)
        self.assertEqual(result['never_attempted_steps'], 7)
        self.assertEqual(result['rejected_decisions'], 153)

    def test_concurrent_worker_seconds_do_not_equal_wall_time(self):
        events = [dict(event=e, format='duel', id=i, time=t)
                  for e, i, t in [('start', 'a', 0), ('start', 'b', 1),
                                  ('complete', 'a', 4), ('complete', 'b', 6), ('start', 'c', 7)]]
        spans, unmatched = intervals(events)
        self.assertEqual(sum(s['end'] - s['start'] for s in spans), 9)
        self.assertEqual(union_seconds((s['start'], s['end']) for s in spans), 6)
        self.assertEqual(unmatched['open_at_end'], 1)

    def test_probe_has_no_optimizer_or_job_entry_point(self):
        tree = ast.parse(Path(__file__).with_name('probe.py').read_text())
        names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse({'step', 'Adam', 'AdamW', 'SGD', 'save', 'run_job'} & names)


if __name__ == '__main__':
    unittest.main()
