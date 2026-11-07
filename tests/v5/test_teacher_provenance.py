"""New teacher labels retain sampling, histories and per-format export identity."""
import copy
import json
import random
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from learning.data import BCSampler, read_shards, validate_record, write_shard
from learning.teachers.provenance import expected_identity, validate_identity, require_rows_teacher
from tests.v5 import helpers


def teacher_row(fmt='duel', teacher='selected_teacher', engine='lite'):
    row = helpers.synthetic_decision_row(format_name=fmt, game_family='family-1')
    row.update(expected_identity(teacher, fmt, engine), source='teacher', engine_id=engine)
    validate_record(row, fmt)
    return row


class TeacherProvenanceTests(unittest.TestCase):
    def test_all_formats_and_backends_validate_actual_teacher_identity(self):
        for fmt in ('duel', 'ffa4', 'team2v2'):
            for engine in ('native', 'lite'):
                teacher = 'gpt6astra' if fmt == 'ffa4' else 'selected_teacher'
                with self.subTest(fmt=fmt, engine=engine):
                    row = teacher_row(fmt, teacher, engine)
                    validate_record(row, fmt)
                    for key in ('teacher_source_sha256', 'teacher_package_sha256', 'teacher_adapter_sha256', 'teacher_strategy'):
                        altered = dict(row, **{key: 'wrong'})
                        with self.assertRaisesRegex(ValueError, 'identity differs'):
                            validate_record(altered, fmt)
        with self.assertRaisesRegex(ValueError, 'labelled Astra'):
            validate_record(dict(teacher_row(), source='astra'))

    def test_new_teacher_uses_the_existing_sampler_distribution_and_rng(self):
        original, modern = [], []
        base = helpers.synthetic_decision_row()
        for pool in ('original', 'dagger'):
            for source in ('astra', 'human'):
                row = copy.deepcopy(base)
                row.update(split='train', data_pool=pool, source=source,
                           token=pool+'/'+source, _history=[])
                original.append(row)
                current = copy.deepcopy(row)
                if source == 'astra':
                    current.update(expected_identity('selected_teacher', 'duel', 'lite'), source='teacher')
                modern.append(current)
        before = BCSampler(original).sample(4000, random.Random(51))
        after = BCSampler(modern).sample(4000, random.Random(51))
        self.assertEqual([r['token'] for r in before], [r['token'] for r in after])
        counts = Counter(r['source'] for r in after)
        self.assertGreater(counts['teacher'], 2800)
        self.assertLess(counts['teacher'], 3200)
        self.assertEqual({r['data_pool'] for r in after}, {'original', 'dagger'})

    def test_new_evaluation_control_is_excluded_from_ppo_rehearsal(self):
        row = teacher_row()
        row.update(split='train', _history=[])
        with self.assertRaisesRegex(ValueError, 'no rehearsal data'):
            BCSampler([row], allow_policy=True, exclude_teacher_impl='selected_teacher')
        with self.assertRaisesRegex(ValueError, 'no rehearsal data'):
            BCSampler([row], allow_policy=True, exclude_teacher_sha=row['teacher_source_sha256'])
        self.assertEqual(BCSampler([row]).sample(1)[0]['teacher'], 'selected_teacher')

    def test_bounded_read_keeps_bucket_order_and_odd_remainder(self):
        base = helpers.synthetic_decision_row()
        with helpers.temporary_directory() as directory:
            paths = [[], []]
            for modern in (0, 1):
                for source in ('astra', 'human'):
                    for family in ('b', 'c', 'd'):
                        rows = []
                        for decision in range(4):
                            row = copy.deepcopy(base)
                            row.update(source=source, game_family=family, decision=decision,
                                       human_control=True, native_version='1.18.8', result_verified=True,
                                       token=f'{source}/{family}/{decision}')
                            if modern and source == 'astra':
                                row.update(expected_identity('selected_teacher', 'duel', 'lite'), source='teacher')
                            rows.append(row)
                        path = directory/str(modern)/(source+family+'.jsonl.gz')
                        write_shard(path, source+family, rows, dict(bots=['fixture']*2, faults=[], winner=1))
                        paths[modern].append(path)
            before = read_shards(paths[0], limit=7, seed=51, format_name='duel')
            after = read_shards(paths[1], limit=7, seed=51, format_name='duel')
            self.assertEqual(len(before), 7)
            self.assertEqual([r['token'] for r in before], [r['token'] for r in after])
            self.assertEqual(sum(r['source'] == 'teacher' for r in after),
                             sum(r['source'] == 'astra' for r in before))

    def test_bc_anchor_pins_and_checks_versioned_teacher_identity(self):
        import torch
        from learning.bc_anchor import ensure_anchor, restore_anchor
        from tests.v5.test_frozen_bc_anchor import make_runner, complete_bc
        with helpers.temporary_directory() as directory:
            runner = make_runner(directory)
            complete_bc(runner)
            path = runner.directory/'last_bc.pt'
            state = torch.load(path, weights_only=False)
            state.update(expected_identity('selected_teacher', 'duel', 'lite'))
            torch.save(state, path)
            ensure_anchor(runner)
            identity = copy.deepcopy(runner.state['frozen_bc_anchor'])
            for key in ('teacher_contract', 'teacher_package_sha256', 'teacher_adapter_sha256'):
                self.assertEqual(identity['teacher'][key], state[key])
            for key in ('teacher_package_sha256', 'teacher_adapter_sha256'):
                runner._bc_anchor = None
                runner.state['frozen_bc_anchor'] = copy.deepcopy(identity)
                runner.state['frozen_bc_anchor']['teacher'][key] = 'wrong'
                with self.assertRaisesRegex(ValueError, 'anchor identity differs'):
                    restore_anchor(runner, {'execution': {'ppo_aux_target': 'frozen_bc_kl'}})

    def test_uncovered_actions_remain_history_but_never_labels(self):
        row = teacher_row()
        missing = copy.deepcopy(row)
        missing.update(choice=-1, turn=1, decision=0)
        matched = copy.deepcopy(row)
        matched.update(turn=2, decision=1)
        with helpers.temporary_directory() as directory:
            path = directory/'teacher.jsonl.gz'
            result = write_shard(path, 'teacher-history', [missing, matched],
                                 dict(bots=['selected_teacher']*2, faults=[], winner=1))
            self.assertEqual((result['written'], result['raw_records']), (1, 2))
            rows = read_shards([path], format_name='duel', expected_teachers={
                'lite': expected_identity('selected_teacher', 'duel', 'lite')})
            self.assertEqual(len(rows), 1)
            self.assertEqual([r['turn'] for r in rows[0]['_history']], [1])
            with self.assertRaisesRegex(ValueError, 'different frozen teacher'):
                read_shards([path], format_name='duel', expected_teachers={
                    'lite': expected_identity('gpt6astra', 'duel', 'lite')})

    def test_corrupt_uncovered_identity_and_mixed_sequence_are_rejected(self):
        from learning.sequences import IndexedSequenceStore
        row = teacher_row()
        with helpers.temporary_directory() as directory:
            with IndexedSequenceStore(directory/'index') as store:
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    store.write([dict(row, choice=-1, teacher_source_sha256='wrong')])
                other = dict(row, **expected_identity('gpt6astra', 'duel', 'lite'))
                with self.assertRaisesRegex(ValueError, 'mixes teacher'):
                    store.write([row, other])

    def test_legacy_rows_stay_readable_but_do_not_count_as_new_supervision(self):
        row = helpers.synthetic_decision_row()
        validate_record(row)
        with self.assertRaisesRegex(ValueError, 'different frozen teacher'):
            require_rows_teacher([row], {'lite': expected_identity('selected_teacher', 'duel', 'lite')})

    def test_mixed_checkpoint_export_keeps_each_formats_identity(self):
        from learning.export import export_checkpoints
        from learning.common import write_json
        identities = {fmt: expected_identity('gpt6astra' if fmt == 'ffa4' else 'selected_teacher', fmt, 'lite')
                      for fmt in ('duel', 'ffa4', 'team2v2')}
        states = {fmt: dict(identity, runner={'version': 1}) for fmt, identity in identities.items()}
        def assemble(models, directory, **kwargs):
            write_json(Path(directory)/'export.json', {'models': {fmt: {} for fmt in models}})
            return Path(directory)/'fixture'
        with helpers.temporary_directory() as directory:
            paths = {fmt: directory/(fmt+'.pt') for fmt in identities}
            for path in paths.values(): path.write_bytes(b'metadata-only fixture')
            with patch('learning.export.load_model', side_effect=lambda path, fmt: (object(), states[fmt])), \
                 patch('learning.export.verify_numerics', return_value=0), \
                 patch('learning.export.export', side_effect=assemble):
                export_checkpoints(paths, directory/'export', audit_records={fmt: [1] for fmt in identities})
                manifest = json.loads((directory/'export/export.json').read_text())
                for fmt, identity in identities.items():
                    self.assertEqual(manifest['models'][fmt]['teacher_strategy'], identity['teacher_strategy'])
                    self.assertEqual(manifest['teacher_identities'][fmt]['teacher_package_sha256'], identity['teacher_package_sha256'])
                states['team2v2']['teacher_source_sha256'] = identities['duel']['teacher_source_sha256']
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    export_checkpoints(paths, directory/'bad', audit_records={fmt: [1] for fmt in identities})


if __name__ == '__main__':
    unittest.main()
