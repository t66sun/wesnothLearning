"""Reward row names change; terminal/step arithmetic and legacy GAE do not."""
import gzip
import unittest

from tests.v5 import helpers


def trajectory():
    rows=helpers.sequence_rows(turns=5,decisions_per_turn=1,source='policy',game_id='b',game_family='b')
    for index,row in enumerate(rows):
        row.update(reward_raw=dict(economy=(index+1)/10,control=(index+2)/10,explored=index/10),
                   reward_after=dict(economy=(index+2)/10,control=(index+3)/10,explored=(index+1)/10),
                   value=.2,log_probability=0.)
    return rows


def write_rows(directory,rows,bootstraps=None,**kwargs):
    from learning.data import write_shard
    from learning.rowpack import unpack_line

    path=directory/'game.jsonl.gz'
    write_shard(path,'b',rows,dict(bots=['a','b'],winner=1,faults={},**kwargs),bootstraps=bootstraps)
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return [unpack_line(line)[0] for line in stream]


class RewardRowSchemaTests(unittest.TestCase):
    def test_schema_five_and_six_gae_are_bit_identical_and_steps_are_audited(self):
        import struct
        from learning.data import advantages

        with helpers.temporary_directory() as directory:
            rows=write_rows(directory,trajectory())
        legacy=[dict({key:value for key,value in row.items() if key not in ('terminal_reward','reward_step')},
                     schema=5,reward=row['terminal_reward']) for row in rows]
        old,new=advantages(legacy),advantages(rows)
        for before,after in zip(old,new):
            self.assertEqual(struct.pack('5d',*before),struct.pack('5d',*after))
        self.assertAlmostEqual(new[0][-1],.675,places=12)
        rows[0]['reward_step']+=.01
        with self.assertRaisesRegex(ValueError,'reward_step differs'):
            advantages(rows)

    def test_truncation_keeps_bootstrap_and_no_terminal_reward_application(self):
        from learning.data import advantages

        raw=trajectory()
        bootstrap=dict(value=.3,turn=6,reward_raw=raw[-1]['reward_after'],potential=0.)
        with helpers.temporary_directory() as directory:
            rows=write_rows(directory,raw,bootstraps={'1':bootstrap},reason='turn_limit',survivors=[1,2])
        self.assertTrue(all(row['truncated'] for row in rows))
        self.assertAlmostEqual(sum(row['reward_step'] for row in rows),.175,places=12)
        self.assertAlmostEqual(advantages(rows)[0][-1],.135,places=12)

    def test_legacy_training_and_homogeneous_schema_six_training(self):
        import torch
        from learning import ppo
        from learning.updates import prepare
        from tests.v5.test_ppo_plan import _records,_run

        legacy=_records([('b',1,0.)])
        self.assertEqual(_run(legacy)[2]['updates'],1)
        with helpers.temporary_directory() as directory:
            rows=write_rows(directory,legacy)
        model=helpers.model(seed=41)
        optimizer=torch.optim.Adam(model.parameters(),lr=1e-4)
        result=ppo.update(model,optimizer,rows,bc_aux=0.,epochs=1)
        self.assertEqual(result['updates'],1)
        with self.assertRaisesRegex(ValueError,'mixes row schemas'):
            prepare(model,rows+legacy)

    def test_row_reward_is_not_the_terminal_value(self):
        with helpers.temporary_directory() as directory:
            rows=write_rows(directory,trajectory())
        self.assertEqual({row['schema'] for row in rows},{6})
        self.assertTrue(all(row['terminal_reward']==1. for row in rows))
        self.assertNotIn('reward',rows[0])
        expected=[.035,.035,.035,.035,.875]
        for row,value in zip(rows,expected):
            self.assertAlmostEqual(row['reward_step'],value,places=12)
        self.assertAlmostEqual(sum(row['reward_step'] for row in rows),1.015,places=12)


if __name__=='__main__':
    unittest.main()
