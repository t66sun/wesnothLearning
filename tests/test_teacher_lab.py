import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lupa import LuaRuntime
from learning.common import ROOT
from learning.formats import FORMATS
from learning.teacher_lab import __main__ as cli
from learning.teacher_lab.packages import compose, digest, read, require_evaluator, stage, write_new
from learning.teacher_lab.panels import GAMES_PER_BLOCK, execute, jobs_for, play, timings
from learning.teacher_lab.report import candidate_cells, compare, provisional, rank_key, score
from learning.teacher_lab.selection import matched_selection, select
import addons


def package(name):
    return dict(name=name,package='/tmp/'+name+'.zip',timeout=1 if name=='astra' else 2,
                first_timeout=10 if name=='astra' else 20)


def schedule(directory, name='search', blocks=1, partition='train', seed=19, offset=0):
    return [job for fmt in FORMATS for horizon in (30,100)
            for job in jobs_for(directory,package(name),package('astra'),fmt,horizon,blocks,
                                partition,9999999999,'wesnoth',seed=seed,offset=offset)]


def outcome(job):
    side=job['meta']['policy_sides'][0];teams=job['teams']
    survivors=[s for s in range(1,len(job['bots'])+1) if teams and teams[s-1]==teams[side-1]] if teams else [side]
    result=dict(bots=job['bots'],winner=side if not teams else 0,teams=teams,
                winning_team=teams[side-1] if teams else 0,survivors=survivors,
                faults={},reason='last_team' if teams else 'last_leader',seconds=600,
                eliminated={str(s):20 for s in range(1,len(job['bots'])+1) if s not in survivors},
                rank_points={str(s):len(job['bots'])-1 if s==side else 0 for s in range(1,len(job['bots'])+1)})
    return dict(id=job['id'],status='complete',result=result,
                timing=dict(decisions=10,mean_ms=20,overruns=[]))


class TeacherLabTests(unittest.TestCase):
    def test_evaluator_rejects_another_archive_or_wrong_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'SOURCE_COMMIT').write_text('commit-a\n')
            manifest=dict(evaluator_root=str(root),source_commit='commit-a')
            with patch('learning.teacher_lab.packages.ROOT',root):
                require_evaluator(manifest)
                with self.assertRaises(ValueError): require_evaluator(dict(manifest,source_commit='commit-b'))
                with self.assertRaises(ValueError): require_evaluator(dict(manifest,evaluator_root=str(root/'other')))

    def test_objectives_and_shared_team_caps(self):
        duel=dict(bots=['a','b'],winner=0,survivors=[1,2],faults={},reason='turn_limit')
        self.assertEqual(score(duel,1,30),1/3)
        self.assertEqual(score(duel,1,100),.5)
        duel.update(winner=2,survivors=[2],reason='last_leader')
        self.assertEqual([score(duel,s,100) for s in (1,2)],[0,1])
        ffa=dict(bots=['a']*4,winner=0,survivors=[2,3],rank_points={'1':0,'2':2.5,'3':2.5,'4':1},
                 faults={},reason='turn_limit')
        self.assertEqual(score(ffa,2,30),2.5/3)
        self.assertEqual([score(ffa,s,100) for s in range(1,5)],[0,.5,.5,0])
        team=dict(ffa,teams=[1,2,1,2],winning_team=0,survivors=[2,3])
        self.assertEqual([score(team,s,100) for s in range(1,5)],[.5]*4)
        team.update(winning_team=1,reason='last_team',survivors=[3])
        self.assertEqual([score(team,s,100) for s in range(1,5)],[1,0,1,0])
        team['faults']={'2':'timeout'}
        with self.assertRaises(ValueError): score(team,1,100)

    def test_frozen_schedule_rotations_budgets_and_scene_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            jobs=schedule(Path(temp)/'a',blocks=12,partition='holdout')
            alternate=schedule(Path(temp)/'b',blocks=12,partition='holdout',seed=91)
        for fmt in FORMATS:
            for horizon in (30,100):
                rows=[j for j in jobs if (j['meta']['format'],j['max_turns'])==(fmt,horizon)]
                self.assertEqual(len(rows),12*GAMES_PER_BLOCK[fmt])
                self.assertEqual(len({j['scenario_family'] for j in rows}),12)
                for block in range(12):
                    group=[j for j in rows if j['meta']['block']==block]
                    self.assertEqual({s for j in group for s in j['meta']['policy_sides']},
                                     set(range(1,len(group[0]['bots'])+1)))
                    for j in group:
                        for s in j['meta']['policy_sides']:
                            self.assertEqual(j['seat_timeouts'][str(s)],dict(timeout=2,first_timeout=20))
                        for s in j['meta']['control_sides']:
                            self.assertEqual(j['seat_timeouts'][str(s)],dict(timeout=1,first_timeout=10))
                        self.assertEqual(j['engine'],'native')
        self.assertEqual([j['scenario_family'] for j in jobs],[j['scenario_family'] for j in alternate])
        self.assertNotEqual([j['seed'] for j in jobs],[j['seed'] for j in alternate])

    def test_complete_blocks_faults_and_seed_clustering(self):
        jobs=schedule(Path('/tmp/one'),blocks=3)
        jobs+=schedule(Path('/tmp/two'),blocks=3,seed=291)
        results=[outcome(j) for j in jobs]
        summary=compare(jobs,results,min_distinct=12)
        for row in summary.values():
            self.assertEqual(row['blocks'],6)
            self.assertEqual(row['distinct_scenarios'],3)
            self.assertEqual(row['difference'],1)
            self.assertFalse(row['passed'])
        summary=compare(jobs,results,min_distinct=3)
        self.assertTrue(all(r['passed'] for r in summary.values()))
        self.assertTrue(provisional(candidate_cells(summary,'search','astra')))
        results[0]['result']['faults']={'1':'timeout'}
        bad=compare(jobs,results)
        affected=bad['search|astra|duel|30']
        self.assertEqual(affected['blocks'],5)
        self.assertEqual(affected['fault_games'],1)
        self.assertFalse(affected['complete'])
        self.assertFalse(provisional(candidate_cells(bad,'search','astra')))
        self.assertIsNone(rank_key(candidate_cells(bad,'search','astra'),'duel'))
        results[0]=dict(id=jobs[0]['id'],status='infrastructure_error')
        self.assertIsNone(rank_key(candidate_cells(compare(jobs,results),'search','astra'),'duel'))

    def test_paired_interval_rejects_equal_or_uncertain_strength(self):
        jobs=schedule(Path('/tmp/equal'),blocks=3);results=[outcome(j) for j in jobs]
        for index,row in enumerate(results):
            j=jobs[index];r=row['result']
            r.update(winner=0,winning_team=0,reason='turn_limit',survivors=list(range(1,len(j['bots'])+1)),
                     rank_points={str(s):(len(j['bots'])-1)/2 for s in range(1,len(j['bots'])+1)})
        for row in compare(jobs,results).values():
            self.assertEqual(row['difference'],0)
            self.assertEqual(row['interval95'],[0,0])
            self.assertFalse(row['passed'])

    def test_timing_and_deadline_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            events=Path(temp)/'events.jsonl'
            events.write_text('\n'.join(json.dumps(dict(event='RETURN',data=r)) for r in [
                dict(side=1,first=True,budget=20,elapsed_ms=1500),
                dict(side=1,first=False,budget=2,elapsed_ms=1900),
                dict(side=2,first=False,budget=1,elapsed_ms=1001)]))
            result=timings(events,[1],{'1':dict(timeout=2,first_timeout=20),'2':dict(timeout=1,first_timeout=10)})
            self.assertEqual(result['decisions'],2)
            self.assertEqual(result['mean_ms'],1700)
            self.assertEqual(len(result['overruns']),1)
            job=schedule(Path(temp)/'expired')[0];job['deadline']=0
            with patch('learning.teacher_lab.panels.match.play_game') as native:
                rows=execute(Path(temp)/'expired',[job])
                native.assert_not_called()
            self.assertEqual(rows[0]['status'],'budget_interrupted')
            self.assertFalse(compare([job],rows)['search|astra|duel|30']['complete'])
            with self.assertRaises(FileExistsError): execute(Path(temp)/'expired',[job])
            job['deadline']=9999999999
            with patch('learning.teacher_lab.panels.match.play_game',side_effect=RuntimeError('bad load')):
                self.assertEqual(play(job)['status'],'infrastructure_error')

    def test_package_composition_preserves_strategy_and_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            choices={fmt:stage(ROOT/'learning/teachers/search_teacher','test_'+fmt,root/(fmt+'.zip'),
                               dict(depth=index+1)) for index,fmt in enumerate(FORMATS)}
            selected=compose(choices,root/'selected.zip')
            with addons.open_addon(selected['package']) as addon:
                dispatch=(addon/'lua/bot.lua').read_text()
                for fmt,row in choices.items():
                    with addons.open_addon(row['package']) as original:
                        for file in (original/'lua').rglob('*.lua'):
                            relocated=file.read_text().replace('~add-ons/'+row['name']+'/lua/',
                                                              '~add-ons/selected_teacher/lua/'+fmt+'/')
                            self.assertEqual((addon/'lua'/fmt/file.relative_to(original/'lua')).read_text(),relocated)
                for fmt in FORMATS:
                    lua=LuaRuntime();lua.globals()['count']=2 if fmt=='duel' else 4
                    lua.globals()['allied']=fmt=='team2v2'
                    lua.execute('''wesnoth={current={side=1},sides={}}
                        for i=1,count do wesnoth.sides[i]={} end
                        function wesnoth.sides.is_enemy(a,b) return not (allied and b==3) end
                        wesnoth.dofile=function(path) return path end''')
                    self.assertEqual(lua.execute(dispatch),'~add-ons/selected_teacher/lua/'+fmt+'/bot.lua')
            with self.assertRaises(FileExistsError): compose(choices,root/'selected.zip')
            Path(choices['duel']['package']).write_bytes(b'changed')
            with self.assertRaises(ValueError): compose(choices,root/'changed.zip')

    def test_clock_is_once_only_and_cannot_extend_registration(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=argparse.Namespace(directory=root)
            write_new(root/'manifest.json',dict(exploration_seconds=18000,selection_seconds=3600,post_seconds=14400))
            with self.assertRaises(ValueError): cli.start(args)
            write_new(root/'panels/pre/plan.json',dict(metadata=dict(preflight=True)))
            write_new(root/'panels/pre/summary.json',{str(i):dict(complete=True,fault_games=0) for i in range(6)})
            with patch('learning.teacher_lab.__main__.time.time',return_value=1000): cli.start(args)
            timer=read(root/'clock.json')
            self.assertEqual(timer,dict(started=1000,exploration_end=19000,selection_end=22600,final_end=33400))
            with self.assertRaises(FileExistsError): cli.start(args)
            with patch('learning.teacher_lab.__main__.time.time',return_value=19000),self.assertRaises(ValueError):
                cli.register(args)
            self.assertEqual(read(root/'clock.json'),timer)
            with patch('learning.teacher_lab.selection.require_evaluator'),\
                    patch('learning.teacher_lab.selection.time.time',return_value=18000),self.assertRaises(ValueError):
                select(root)

    def test_selection_matches_common_blocks_and_rejects_faulted_contenders(self):
        jobs=schedule(Path('/tmp/validate'),'a',blocks=2)+schedule(Path('/tmp/validate'),'b',blocks=2)
        results=[outcome(j) for j in jobs]
        missing=next(j for j in jobs if j['meta']['candidate']=='b' and j['meta']['format']=='duel' and j['meta']['block']==1)
        results=[r for r in results if r['id']!=missing['id']]
        shortlist={fmt:[dict(name='a'),dict(name='b')] for fmt in FORMATS}
        rows=matched_selection(jobs,results,shortlist)
        self.assertEqual(rows['a|astra|duel|30']['blocks'],1)
        self.assertEqual(rows['b|astra|duel|30']['blocks'],1)
        next(r for r in results if r['id'].startswith('validate-b-astra-30-ffa4'))['result']['faults']={'1':'timeout'}
        rows=matched_selection(jobs,results,shortlist)
        self.assertNotIn('b|astra|ffa4|30',rows)
        self.assertNotIn('b|astra|ffa4|100',rows)

    def test_post_phase_freezes_design_before_validation_and_selected_before_holdout(self):
        self.post_phase()

    def test_unqualified_selection_cannot_pass_using_holdout(self):
        self.post_phase(fallback=True)

    def post_phase(self,fallback=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=ROOT/'learning/teachers/search_teacher'
            baseline=stage(ROOT/'learning/teachers/gpt6astra','astra',root/'astra.zip')
            candidate=stage(source,'candidate',root/'candidate.zip',{})
            candidate.update(registered=500,source_commit='source')
            write_new(root/'candidates/candidate/candidate.json',candidate)
            write_new(root/'manifest.json',dict(baseline=baseline,source_commit='source',workers=8,
                                               executable='wesnoth',min_distinct=12))
            write_new(root/'clock.json',dict(started=0,exploration_end=18000,selection_end=21600,final_end=32400))
            train=schedule(Path('/tmp/train'),'candidate',blocks=3)
            def fake_execute(directory,jobs,**kwargs):
                self.assertTrue((root/'selection/holdout_design.json').is_file())
                directory.mkdir()
                if directory.name=='holdout':
                    chosen=read(root/'selection/selected.json')
                    self.assertEqual(digest(chosen['package']),chosen['package_sha256'])
                    self.assertTrue(all(j['deadline']==32400 for j in jobs))
                else:
                    self.assertFalse((root/'selection/selected.json').exists())
                    self.assertTrue(all(j['deadline']==21600 for j in jobs))
                return [outcome(j) for j in jobs]
            with patch('learning.teacher_lab.selection.time.time',return_value=18001),\
                    patch('learning.teacher_lab.selection.require_evaluator'),\
                    patch('learning.teacher_lab.selection.load_panels',return_value=(train,[outcome(j) for j in train])),\
                    patch('learning.teacher_lab.selection.matched_selection',
                          side_effect=lambda *args:{} if fallback else matched_selection(*args)),\
                    patch('learning.teacher_lab.selection.execute',side_effect=fake_execute):
                select(root)
            final=read(root/'final.json')
            self.assertEqual(final['passed'],not fallback)
            self.assertEqual(all(final['selected']['qualified'].values()),not fallback)
            self.assertEqual(len(final['comparison']),6)
            self.assertTrue(all(r['distinct_scenarios']>=12 for r in final['comparison'].values()))
            self.assertEqual(set(final['selected']['basis'].values()),
                             {'unqualified_exploration_fallback' if fallback else 'matched_validation'})


if __name__=='__main__':
    unittest.main()
