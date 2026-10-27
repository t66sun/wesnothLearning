"""PPO rehearsal excludes its evaluation control; BC retains teacher labels."""
import random
import unittest

from tests.v5.test_ppo_plan import _bc, _records


def human_rows():
    rows = _bc()
    for row in rows:
        row.update(source='human', teacher=None, teacher_impl=None,
                   teacher_source_sha256=None, human_control=True,
                   native_version='1.18.8', value_valid=False)
    return rows


class RehearsalSourceTests(unittest.TestCase):
    def test_runner_refuses_control_only_pool_before_parameter_change(self):
        import torch
        from unittest.mock import patch
        from learning import ppo
        from tests.test_validation_cadence import ValidationCadenceTests
        from tests.v5 import helpers

        rows = _records([('b',1,0.)])
        with helpers.temporary_directory() as directory:
            runner=ValidationCadenceTests().runner(directory)
            runner.config.update(engine='lite',epochs=1)
            runner.model=helpers.model(seed=41)
            runner.optimizer=torch.optim.Adam(runner.model.parameters(),lr=1e-4)
            runner.update_deadline=lambda:float('inf')
            runner.state['pending_train']=dict(method='ppo',paths=['policy'],cursor={})
            before=ppo._digest(runner.model)
            with patch('learning.experiment.read_shards',side_effect=lambda paths,**kw:rows if paths==['policy'] else _bc()), \
                 self.assertRaisesRegex(ValueError,'no rehearsal data distinct from the evaluation control'):
                runner.finish_train()
            self.assertEqual(ppo._digest(runner.model),before)
            self.assertEqual(runner.state['version'],0)

    def test_sha_exclusion_does_not_confuse_environment_with_label_source(self):
        from learning.data import BCSampler

        teacher = _bc()
        for row in teacher:
            row['teacher_source_sha256'] = 'control-sha'
        human = human_rows()
        for row in human:
            row['teacher_source_sha256'] = 'control-sha'  # environment provenance only
        sampler = BCSampler(teacher+human,exclude_teacher_sha='control-sha')
        self.assertEqual(sampler.rows_excluded, 2)
        self.assertEqual({row['source'] for row in sampler.sample(20)},{'human'})

    def test_twenty_updates_report_only_distinct_human_rehearsal(self):
        import torch
        from learning import ppo
        from tests.v5 import helpers

        rows = _records([('b',1,0.)])
        rehearsal = _bc()+human_rows()
        for _ in range(20):
            model = helpers.model(seed=41)
            optimizer = torch.optim.Adam(model.parameters(),lr=1e-4)
            result = ppo.update(model,optimizer,rows,bc_records=rehearsal,epochs=1,
                                rehearsal_exclude=dict(impl='gpt6astra'))
            self.assertEqual(result['rehearsal_rows_excluded'],2)
            self.assertEqual(result['rehearsal_sources'],[dict(source='human',teacher_impl=None,sha256=None)])
            self.assertEqual(result['committed_steps'],1)

    def test_empty_pool_fails_only_when_auxiliary_loss_is_enabled(self):
        import torch
        from learning import ppo
        from tests.v5 import helpers

        rows = _records([('b',1,0.)])
        model = helpers.model(seed=41)
        optimizer = torch.optim.Adam(model.parameters(),lr=1e-4)
        with self.assertRaisesRegex(ValueError,'no rehearsal data distinct from the evaluation control'):
            ppo.update(model,optimizer,rows,bc_records=_bc(),epochs=1,
                       rehearsal_exclude=dict(impl='gpt6astra'))
        result = ppo.update(model,optimizer,rows,bc_records=None,epochs=1,bc_aux=0.,
                            rehearsal_exclude=dict(impl='gpt6astra'))
        self.assertEqual(result['committed_steps'],1)
        self.assertEqual(result['rehearsal_sources'],[])

    def test_control_policy_cannot_rehearse(self):
        from learning.data import BCSampler

        with self.assertRaisesRegex(ValueError, 'no rehearsal data distinct from the evaluation control'):
            BCSampler(_bc(), exclude_teacher_impl='gpt6astra')
        sampler = BCSampler(_bc()+human_rows(), exclude_teacher_impl='gpt6astra')
        self.assertEqual({row['source'] for row in sampler.sample(20,rng=random.Random(19))},{'human'})
        self.assertEqual(sampler.rows_excluded, 2)
        # BC has no exclusion and still accepts exactly the same teacher data.
        self.assertEqual({row['source'] for row in BCSampler(_bc()).sample(2)},{'astra'})


if __name__ == '__main__':
    unittest.main()
