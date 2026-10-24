import copy,gzip,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import torch
from learning.common import write_json
from learning.data import read_shards,write_shard,split,advantages
from learning.experiment import default_config,validate_config,coverage_gate
from learning.schedule import teacher_jobs,evaluation_jobs
from learning.evaluate import comparisons,selection_key
from learning.train import imitation_quality
from learning.sample import opening_map
from tests.test_core import record
import tests.test_validation_cadence as cadence_fixtures


class RevisionTests(unittest.TestCase):
    def family(self,part,index=0):
        return next(f'family-{i}' for i in range(index,100000) if split(f'family-{i}')==part)

    def test_targets_and_cpu_preset(self):
        config=default_config('cpu');validate_config(config)
        self.assertEqual(config['bc_games'],dict(duel=300,ffa4=600,team2v2=400))
        self.assertEqual((config['workers'],config['trainer_threads']),(8,1))
        self.assertEqual(config['validation_games']['team2v2'],8)
        with self.assertRaises(ValueError):validate_config(config|dict(validation_games=dict(duel=6,ffa4=4,team2v2=4)))

    def test_teacher_batches_have_unique_ids_and_baseline_partner(self):
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            groups=[teacher_jobs('.', ['gpt6astra.zip'],['gpt6astra.zip','baseline'],'support',b,17,3000000000,'unused',
                formats=['team2v2'],count=n,index_stride=8) for b,n in [(0,8),(1,3),(2,8)]]
        jobs=sum(groups,[]);self.assertEqual(len({j['id'] for j in jobs}),19)
        self.assertEqual(len({j['seed'] for j in jobs}),19)
        for j in jobs:
            side=j['meta']['seat'];ally=next(s for s in range(1,5) if s!=side and j['teams'][s-1]==j['teams'][side-1])
            self.assertEqual(j['bots'][ally-1],'baseline')

    def test_bounded_pool_rotates_more_than_eight_families_without_leakage(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for i in range(80):
                family=f'game-{i}';row=record();row.update(game_id=family,game_family=family,split=split(family))
                path=Path(temp)/f'{i}.gz'
                with gzip.open(path,'wt') as f:
                    for _ in range(20):f.write(json.dumps(row)+'\n')
                paths.append(path)
            pools=[read_shards(paths,partition='train',limit=192,seed=s,format_name='duel') for s in (19,20)]
            # A bounded read admits as many families as the request needs: the old
            # limit//32 pool could not fill 192 rows from twenty-row games.
            self.assertEqual([len(pool) for pool in pools],[192,192])
            families=[{r['game_family'] for r in pool} for pool in pools]
            self.assertEqual(len(families[0]),10)
            self.assertGreater(len(families[0]),1)
            self.assertNotEqual(families[0],families[1])
            validation=read_shards(paths,partition='validation',limit=192,seed=19,format_name='duel')
            self.assertFalse(set.union(*families)&{r['game_family'] for r in validation})

    def test_truncation_bootstraps_and_potential_telescopes(self):
        row=record();row.update(truncated=True,bootstrap_value=.8,potential=.2,bootstrap_potential=.4,
            reward_raw=dict(economy=0.,control=0.,explored=.1),
            bootstrap_raw=dict(economy=0.,control=0.,explored=.2))
        adv,returns=advantages([row]);self.assertAlmostEqual(adv[0],.61);self.assertAlmostEqual(returns[0],.81)
        row['bootstrap_value']=None
        with self.assertRaises(ValueError):advantages([row])
        rows=[dict(record(index=i),turn=i+1,reward=0.,value=0.,reward_raw=dict(economy=p,control=0.,explored=0.)) for i,p in enumerate((.2,.4))]
        _,returns=advantages(rows,lam=1.)
        # Potential shaping telescopes: the sum equals the terminal value minus
        # the initial potential, so the terminal transition removes the balance.
        self.assertAlmostEqual(returns[1],-.15*.4)
        self.assertAlmostEqual(returns[0],-.15*.2)

    def test_faults_are_excluded_and_truncated_teacher_value_is_masked(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'data.gz';result=dict(bots=['a','b'],winner=0,faults={'2':'teacher assertion'},reason='last_leader')
            report=write_shard(path,'game',[record()],result)
            self.assertEqual(report['excluded'],'faulted_game');self.assertEqual(read_shards([path]),[])
            result.update(faults={},reason='turn_limit')
            write_shard(path,'game',[record()],result)
            row=read_shards([path])[0];self.assertFalse(row['value_valid']);self.assertAlmostEqual(row['reward'],0.)
            policy=dict(record(),source='policy',teacher=False,potential=.2)
            self.assertEqual(write_shard(path,'game',[policy],result)['excluded'],'missing_truncation_bootstrap')
            write_shard(path,'game',[policy],result,{'1':dict(value=.6,potential=.3)})
            self.assertAlmostEqual(read_shards([path])[0]['bootstrap_value'],.6)
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            jobs=evaluation_jobs('.', 'p','baseline',['baseline'],1,1,3000000000,'unused',formats=['duel'])
        results=[dict(id=j['id'],status='complete',result=dict(bots=j['bots'],winner=1,faults={'2':'error'})) for j in jobs]
        comparison=comparisons(jobs,results,min_blocks=1)
        self.assertEqual(comparison['duel']['fault_games'],2);self.assertIsNone(selection_key(comparison))

    def test_validation_rotates_six_factions_and_pairs_same_team_policy(self):
        all_factions=set()
        for cycle in range(3):
            with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
                jobs=evaluation_jobs('.', 'same-policy','baseline',['baseline'],1,17,3000000000,'unused',formats=['team2v2'],faction_cycle=cycle)
            self.assertEqual(len(jobs),8)
            self.assertEqual({j['meta']['policy'] for j in jobs},{'same-policy'})
            self.assertEqual({j['meta']['context'] for j in jobs},{'baseline_partner','self_team'})
            all_factions.update(f for j in jobs for f in j['factions'])
        self.assertEqual(len(all_factions),6)

    def test_corpus_gate_blocks_early_ppo_even_with_good_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            r=cadence_fixtures.ValidationCadenceTests().runner(temp,'duel');r.state['version']=10
            write_json(Path(temp)/'bc_gate.json',dict(imitation=dict(effective=True),coverage=dict(passed=True),
                corpus=dict(games=20,required=1600,passed=False),opening=dict(passed=False)))
            calls=[];r.execute=lambda jobs,name:(calls.append(name) or jobs,[])
            with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
                r.validate_model('bc')
            self.assertEqual(calls,['validation-000010']);self.assertFalse(r.state['effective'])

    def test_kind_metrics_reject_weak_movement_despite_high_overall_accuracy(self):
        class Fixed(torch.nn.Module):
            def __init__(self):super().__init__();self.anchor=torch.nn.Parameter(torch.zeros(1))
            format_name='duel'
            def forward(self,g,o,a,om,am,payload):
                logits=torch.zeros(a.shape[:2]);logits[:,0]=6
                return logits,torch.zeros(a.shape[0])
        rows=[]
        for kind in ('recruit','move','attack'):
            for _ in range(32):
                row=record();row.update(split='validation',choice=1 if kind=='move' else 0,actual=dict(kind=kind))
                rows.append(row)
        quality=imitation_quality(Fixed(),rows)
        self.assertFalse(quality['effective']);self.assertEqual(quality['formats']['duel']['kinds']['move']['accuracy'],0)


if __name__=='__main__':unittest.main()
