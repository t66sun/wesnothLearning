"""V5: frozen rollout identity binds target IDs, training values and raw prefixes."""
import copy
import hashlib
import unittest
from unittest.mock import Mock, patch

from learning.data import validate_record
from learning.rowpack import compact_row, pack_line, unpack_line
from learning.updates import rollout_identity
from tests import test_validation_cadence as cadence
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _records, _bc


class RolloutContentIdentityTests(unittest.TestCase):
    def test_hashes_one_buffer_per_target_and_shared_prefix(self):
        slot = dict(turn=1, floats=[-0., 0.125])
        rows = [dict(turn=2, decision=i, choice=0, _history=[slot], values=[1, 1.e-12, -0.0]) for i in (1, 2)]
        sha256 = hashlib.sha256
        payloads = []
        def track(initial=b''):
            digest = Mock(wraps=sha256(initial))
            if initial != b'rollout-content-v2\n':
                payloads.append((bool(initial), digest))
            return digest
        with patch('learning.updates.hashlib.sha256', side_effect=track):
            identity = rollout_identity(rows)
        self.assertEqual(identity, '4c22a9676c4886e0b505807ee6c16a856a2609dcbd4bcdaf8ca9fd5116426196')
        self.assertEqual([int(initial) + h.update.call_count for initial, h in payloads], [1, 1, 1])

    def changes(self, row):
        for key,value in [('game_id','other'),('side',2),('turn',3),('decision',99),
                          ('log_probability',-4.),('reward',-.5),('value',.7),('bootstrap_value',.8),
                          ('truncated',True),('version',8),('candidate_version','other')]:
            changed=copy.deepcopy(row)
            changed[key]=value
            yield key,changed
        for name,path in [('observation',('global',0)),('action',('candidates',0,'features',0)),
                          ('geometry',('candidates',0,'geometry',0)),('local',('candidates',0,'local',0)),
                          ('board',('spatial','board',0,0,0)),('history',('_history',0,'global',0)),
                          ('raw-reward',('reward_raw','economy')),('reward-after',('reward_after','economy'))]:
            changed=copy.deepcopy(row)
            part=changed
            for key in path[:-1]: part=part[key]
            part[path[-1]]+=.125
            yield name,changed
        changed=copy.deepcopy(row)
        changed['choice']=(changed['choice']+1)%len(changed['candidates'])
        changed['actual']=copy.deepcopy(changed['candidates'][changed['choice']])
        yield 'choice',changed

    def test_changed_valid_inputs_rejected_before_any_update(self):
        row=_records([('b',2,0.)])[-1]
        validate_record(row)
        original=rollout_identity([row])
        rehearsal=_bc()
        with helpers.temporary_directory() as directory:
            r=cadence.ValidationCadenceTests().runner(directory)
            r.state['pending_train']=dict(method='ppo',paths=['policy'],cursor={},
                identity=dict(train=original,bc=rollout_identity(rehearsal)))
            for name,changed in self.changes(row):
                with self.subTest(field=name):
                    validate_record(changed)
                    self.assertNotEqual(rollout_identity([changed]),original,name)
                    with patch('learning.experiment.read_shards',side_effect=lambda paths,**kw: [changed] if paths==['policy'] else rehearsal), patch('learning.experiment.train') as train:
                        with self.assertRaisesRegex(ValueError,'scheduled rollout changed'):
                            r.finish_train()
                        train.assert_not_called()

    def test_unchanged_rereads_and_container_forms_match(self):
        rows=_records([('b',2,0.),('c',3,0.)])
        self.assertEqual(rollout_identity(rows),rollout_identity(copy.deepcopy(list(reversed(rows)))))
        self.assertEqual(rollout_identity(rows),rollout_identity(compact_row(copy.deepcopy(rows))))
        # Actual packed input rereads are stable; disk float32 is not claimed equal to float64.
        packed=[unpack_line(pack_line(row))[0] for row in rows]
        reread=[unpack_line(pack_line(row))[0] for row in rows]
        self.assertEqual(rollout_identity(packed),rollout_identity(reread))


if __name__ == '__main__':
    import torch
    torch.set_num_threads(1)
    unittest.main()
