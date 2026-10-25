"""V2: actual last/best/selected checkpoint writers reach checked export."""
import copy
import unittest
from unittest.mock import patch

import torch

from learning.common import read_json, write_json
from learning.experiment import FormatExperiment
from learning.export import export_checkpoints
from tests import test_validation_cadence as cadence
from tests.v5 import helpers


class CheckpointExportIdentityTests(unittest.TestCase):
    def test_last_best_selected_keep_identity_and_finished_bookkeeping(self):
        with helpers.temporary_directory() as directory:
            paths = {}
            audit = {}
            for fmt in ('duel', 'ffa4', 'team2v2'):
                folder = directory/fmt
                folder.mkdir()
                write_json(directory/'manifest.json', dict(test='V2'))
                r = cadence.ValidationCadenceTests().runner(folder, fmt)
                r.config['engine'] = 'lite'
                r.controller.state_dict = lambda: {}
                r.model = helpers.model(format_name=fmt)
                r.optimizer = torch.optim.Adam(r.model.parameters())
                r.state['version'] = 99
                r.state['pending_train'] = dict(method='ppo', paths=['rollout'], cursor={})
                r.save = lambda: FormatExperiment.save(r)
                with patch('learning.experiment.read_shards', return_value=[]), patch('learning.experiment.train', return_value=dict(interrupted=False, updates=1, committed_decisions=4)):
                    r.finish_train()
                def execute(jobs, name):
                    return jobs, [dict(id=j['id'],status='complete',result=dict(bots=j['bots'],teams=j.get('teams'),
                        winner=j['meta']['policy_sides'][0], winning_team=(j.get('teams') or [None]*4)[j['meta']['policy_sides'][0]-1],
                        rank_points={str(s):3 if s in j['meta']['policy_sides'] else 0 for s in range(1,5)},faults={})) for j in jobs]
                r.execute = execute
                with patch('learning.maps.frozen_map', return_value=('Gg,Gg\nGg,Gg','0'*64)):
                    r.validate_model('ppo')
                selected, kind, _ = r._select_final()
                self.assertEqual(kind, 'champion')
                for name in ('latest.pt', 'last_ppo.pt', 'best_ppo.pt', 'best.pt', 'selected.pt'):
                    saved = torch.load(folder/name, weights_only=False)
                    for key, value in r.identity().items(): self.assertEqual(saved.get(key), value, (fmt,name,key))
                    self.assertEqual(saved['manifest_sha256'], __import__('learning.common',fromlist=['sha256']).sha256(directory/'manifest.json'))
                    self.assertEqual(saved['execution']['plan_version'], 2)
                    if name.startswith('best') or name == 'selected.pt':
                        self.assertIsNone(saved['runner']['pending_validation'])
                        self.assertEqual(saved['runner']['best_key'], r.state['best_key'])
                paths[fmt] = selected
                rows = helpers.sequence_rows(turns=2, decisions_per_turn=1, format_name=fmt)
                audit[fmt] = [helpers.pad_candidates(row,128) for row in rows]
            # Isolate metadata/numerics from the unchanged SDK archive-size gate.
            # No submission/package acceptance is claimed by this test.
            def assemble(models, destination, **kwargs):
                self.assertEqual(set(models), set(paths))
                write_json(destination/'export.json', dict(models={fmt:{} for fmt in paths}))
                return destination
            with patch('learning.export.export', side_effect=assemble):
                export_checkpoints(paths, directory/'export', audit_records=audit)
            manifest = read_json(directory/'export/export.json')
            for fmt,path in paths.items():
                saved = torch.load(path, weights_only=False)
                for key in ('engine','engine_version','rng_version','combat_version','teacher','teacher_profile','teacher_source_sha256'):
                    self.assertEqual(manifest['models'][fmt][key], saved[key])
                self.assertLessEqual(manifest['models'][fmt]['python_lua_max_error'], 1e-5)
            bad = torch.load(paths['duel'], weights_only=False)
            for key in ('combat_version', 'teacher_profile', 'teacher_source_sha256'):
                changed = copy.deepcopy(bad)
                changed[key] = 'wrong'
                torch.save(changed, directory/'bad.pt')
                with self.assertRaisesRegex(ValueError, 'identity'):
                    export_checkpoints(dict(paths,duel=directory/'bad.pt'),directory/('bad-'+key),audit_records=audit)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
