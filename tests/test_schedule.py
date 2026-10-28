import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from learning.common import ROOT
from learning.formats import FORMATS,TEAM2V2
from learning.schedule import rollout_jobs,teacher_jobs,evaluation_jobs,freeze_schedule
from learning.evaluate import comparisons,control_comparisons,overall_status,bootstrap,selection_key
from learning.data import reward,infer_format
from learning.experiment import default_config,validate_config,read_log
import native
import teams


class ScheduleTests(unittest.TestCase):
    def test_team_assignment_and_credit(self):
        self.assertEqual(teams.validate(TEAM2V2,4),[1,2,1,2])
        result=dict(bots=['a','b','a','b'],**teams.adjudicate(TEAM2V2,[3],{}))
        self.assertEqual(result['winners'],[1,3])
        self.assertEqual(reward(result,1),1.)
        self.assertEqual(reward(result,2),-1.)
        self.assertEqual(infer_format(result),'team2v2')
        fault=teams.adjudicate(TEAM2V2,[1,2,3,4],{1:'fault'})
        self.assertEqual(fault['winning_team'],2)
        self.assertEqual(teams.adjudicate(TEAM2V2,[1,2],{})['winning_team'],0)

    def test_wml_teams_are_opt_in(self):
        config=dict(fog=True,max_turns=30,teams=TEAM2V2)
        wml=native.scenario(config,['Drakes']*4)
        self.assertEqual(wml.count('team_name=team_1\n'),2)
        self.assertEqual(wml.count('team_name=team_2\n'),2)
        self.assertIn('share_view=yes',wml)
        del config['teams']
        self.assertIn('team_name=side_4',native.scenario(config,['Drakes']*4))

    def test_official_ai_in_all_team_roles(self):
        fixed=['gpt6astra.zip','baseline']
        from learning.sample import opening_map
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            jobs=rollout_jobs(ROOT/'tmp','learner',['history'],fixed,'support','v1',0,19,1000,'wesnoth')
        enemy_roles=[];team_jobs=[]
        for j in jobs:
            enemy_roles.extend(c['role'] for c in j['meta']['composition'] if c['role']!='teammate')
            if j['meta']['format']=='team2v2': team_jobs.append(j)
        self.assertEqual(enemy_roles.count('fixed'),len(enemy_roles)//2)
        self.assertEqual(enemy_roles.count('history'),len(enemy_roles)//4)
        self.assertEqual(enemy_roles.count('current'),len(enemy_roles)//4)
        self.assertEqual(sum(c['role']=='teammate' and c['path']=='baseline' for j in team_jobs for c in j['meta']['composition']),1)
        teachers=teacher_jobs(ROOT/'tmp',fixed[:-1],fixed,'support',0,1,1000,'wesnoth')
        for j in teachers:
            if j['meta']['format']=='team2v2':
                side=j['meta']['seat'];allied=[s for s in range(1,5) if s!=side and j['teams'][s-1]==j['teams'][side-1]]
                self.assertEqual(j['bots'][allied[0]-1],'baseline')
        from learning.sample import opening_map
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            evals=evaluation_jobs(ROOT/'tmp','learner','baseline',fixed,1,1,1000,'wesnoth')
        self.assertEqual({j['meta']['context'] for j in evals if j['meta']['format']=='team2v2'},{'baseline_partner','self_team'})

    def test_frozen_schedule(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'jobs.json'
            h=freeze_schedule(p,[dict(id='a')]);self.assertEqual(freeze_schedule(p,[dict(id='a')]),h)
            with self.assertRaises(ValueError): freeze_schedule(p,[dict(id='b')])

    def test_two_controls_are_never_merged_and_opening_fixture_is_safe(self):
        from learning.sample import opening_map
        from learning.sample import opening_map
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            a=evaluation_jobs(ROOT/'tmp','policy','gpt6astra.zip',['baseline'],1,1,1000,'unused',formats=['duel'],label='astra')
            b=evaluation_jobs(ROOT/'tmp','policy','baseline',['baseline'],1,1,1000,'unused',formats=['duel'],label='baseline')
        with self.assertRaises(ValueError): comparisons(a+b,[])
        summary=control_comparisons(a+b,[])
        self.assertEqual(set(summary['duel']),{'gpt6astra.zip','baseline'})
        self.assertEqual(summary['duel']['baseline']['planned_blocks'],1)
        board=opening_map(4)
        self.assertTrue(all(b[0]-a[0]>=128 for a,b in zip(board['starts'],board['starts'][1:])))
        for x,y in board['starts']:
            self.assertEqual(board['terrain'][y-1][x-1],'Kh')
            self.assertEqual(board['terrain'][y-1][x+3],'Gg^Vh')

    def test_block_bootstrap_and_incomplete_blocks(self):
        from learning.sample import opening_map
        repeated={fmt:[dict(map_index=0,faction_block=0)] for fmt in FORMATS}
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            jobs=evaluation_jobs(ROOT/'tmp','a','b',['baseline'],30,123,1000,'wesnoth',
                                 scenarios=repeated)
        results=[]
        for j in jobs:
            sides=j['meta']['policy_sides'];side=sides[0]
            n=len(j['bots'])
            result=dict(bots=j['bots'],winner=side,faults={},rank_points={s:n-1 if s in sides else 0 for s in range(1,n+1)})
            if j['teams']: result.update(teams.adjudicate(j['teams'],sides,{}))
            results.append(dict(id=j['id'],status='complete',result=result))
        summary=comparisons(jobs,results)
        self.assertEqual(overall_status(summary),'insufficient_design')
        self.assertEqual(summary['team2v2']['blocks'],30)
        self.assertIsNone(selection_key({'duel':summary['duel']}))
        with self.assertRaises(ValueError): selection_key(summary)
        missing=comparisons(jobs,results[:-1])
        self.assertEqual(overall_status(missing),'insufficient_design')
        self.assertIsNone(selection_key({'team2v2':missing['team2v2']}))
        self.assertEqual(bootstrap([0.,0.]),[0.,0.])
        incomplete=results.copy();incomplete[0]=dict(id=jobs[0]['id'],status='infrastructure_error')
        self.assertEqual(overall_status(comparisons(jobs,incomplete)),'infrastructure_error')

    def test_deadline_config_and_log_recovery(self):
        cfg=default_config();validate_config(cfg)
        for invalid in [dict(hours=0),dict(final_blocks=29),dict(workers=17),dict(rollout_games=3)]:
            with self.assertRaises(ValueError): validate_config(cfg|invalid)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'jobs.jsonl';p.write_bytes(b'{"id":"done","status":"complete"}\n{"id":"cut')
            self.assertEqual(read_log(p),[dict(id='done',status='complete')])

    def test_linux_command_omits_windows_only_option(self):
        from types import SimpleNamespace
        native.check_version.cache_clear()
        with patch('native.os.name','posix'),patch('native.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='1.18.8\n')) as proc:
            self.assertEqual(native.check_version('not-an-executable-fixture'),'1.18.8')
            self.assertNotIn('--wnoconsole',proc.call_args.args[0])
        native.check_version.cache_clear()


if __name__=='__main__': unittest.main()
