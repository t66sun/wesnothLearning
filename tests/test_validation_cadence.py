"""Focused smoke checks for ten updates per native validation."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
from learning.common import read_json, write_json
from learning.experiment import FormatExperiment, default_config, validate_config
from learning.schedule import evaluation_jobs
from learning.evaluate import comparisons


class ValidationCadenceTests(unittest.TestCase):
    def test_collector_survives_dead_or_advanced_native_handle(self):
        from tests.test_lua_contracts import initialize
        from learning.common import ROOT
        for advanced in (False,True):
            lua,modules=initialize()
            modules['config.lua']=lua.eval('{candidate_budget_ms=200}')
            modules['runtime.lua']=lua.eval('{emit=function(kind,row) records[#records+1]=row end}')
            lua.globals().advanced=advanced
            lua.execute('''
                records={}
                ai.move=function(u,p) u.x=p[1];u.y=p[2];u.moves=u.moves-1;return {ok=true,gamestate_changed=true} end
                ai.attack=function(u,e,w)
                    local old=fixture.own[1]
                    local replacement=old:clone()
                    fixture.own=advanced and {replacement,fixture.own[2]} or {fixture.own[2]}
                    fixture.visible={fixture.own[1],fixture.own[2]}
                    for k in pairs(old) do old[k]=nil end
                    setmetatable(old,{__index=function() error('unknown unit') end})
                    return {ok=true,gamestate_changed=true}
                end
            ''')
            collector=lua.execute((ROOT/'learning/collector.lua').read_text(encoding='utf-8-sig'))
            data=lua.eval('{plan={kind="combat",tx=3,ty=2,ex=3,ey=1,weapon=1}}')
            lua.execute('fixture.judge=true')
            undo=collector.wrap(data,lua.eval('{teacher="gpt6astra",version="fixture"}'))
            lua.execute('ai.move(fixture.own[1],{3,2});ai.attack(fixture.own[1],{3,1},1)')
            undo(True)
            row=lua.globals().records[1]
            self.assertIsNotNone(row)
            self.assertEqual(row['outcome']['alive'],advanced)
            self.assertGreaterEqual(row['choice'],0)
            self.assertEqual(row['diagnostics']['remaining_moves'],8)

    def runner(self,root,fmt='duel'):
        r=FormatExperiment.__new__(FormatExperiment)
        from learning.manifest import teacher_identity
        r.teacher_record=teacher_identity('gpt6astra')  # Explicit legacy fixture.
        r.manifest=dict(teacher=r.teacher_record)
        r.reference_opponents=['gpt6astra.zip','baseline']
        r.directory=Path(root);r.fmt=fmt;r.config=default_config(engine='native')
        r.clock=dict(started=0,update_deadline=3000000000.)
        r.state=dict(batch=0,version=0,history=[],pending_train=None,pending_validation=None,
            teacher_shards=[],dagger_shards=[],snapshots=[],effective=False,best_key=None,bc_key=None,ppo_key=None,
            counters=dict(optimizer_steps=0,decisions_seen=0,unique_families_seen=0,effective_dataset_passes=0.))
        r.support='support'
        r.controller=type('Controller',(),{'freeze':lambda self:dict(mode='fixed',entropy=.01,bc_aux=.1)})()
        r.model=None;r.optimizer=None;r.teachers=['gpt6astra.zip'];r.fixed=['gpt6astra.zip','baseline'];r.exe='unused'
        r.save=lambda:write_json(r.directory/'state.json',r.state)
        r.human_paths=lambda:[]
        r.ensure_export=lambda *a,**k:'policy'
        write_json(r.directory/'controls.json',dict(controls={fmt:'baseline'}))
        return r

    def test_tenth_update_and_checkpointed_pending_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            r=self.runner(temp)
            with patch('learning.experiment.read_shards',return_value=[]),patch('learning.experiment.train',return_value=dict(interrupted=False,updates=4,loss=1)),patch('learning.experiment.imitation_quality',return_value=dict(effective=False)),patch('learning.experiment.FormatExperiment._write_checkpoint'):
                for i in range(1,11):
                    r.state['pending_train']=dict(method='bc',paths=[],cursor={})
                    with patch('learning.experiment.imitation_quality',return_value=dict(effective=False,formats={r.fmt:dict(accuracy=0.)})):
                        self.assertTrue(r.finish_train())
                    self.assertEqual(r.state['batch'],i)
                    self.assertEqual(r.state['pending_validation'],'bc' if i==10 else None)
            self.assertEqual(read_json(Path(temp)/'state.json')['pending_validation'],'bc')

    def test_validation_sizes_paired_contexts_and_no_unready_opening(self):
        for fmt,expected in [('duel',6),('ffa4',4),('team2v2',8)]:
            with tempfile.TemporaryDirectory() as temp:
                r=self.runner(temp,fmt);seen=[]
                def execute(jobs,name):
                    seen.append(jobs)
                    return jobs,[]
                r.execute=execute
                write_json(Path(temp)/'bc_gate.json',dict(imitation=dict(effective=False),coverage=dict(passed=True),opening=dict(passed=False)))
                from learning.sample import opening_map
                with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
                    for version in (10,20):
                        r.state.update(version=version,batch=version,pending_validation='bc')
                        r.validate_model('bc')
                    self.assertEqual(len(seen[-1]),expected)
                    self.assertEqual(r.state['batch'],version)
                self.assertEqual(len(seen),2,'unready BC must not launch opening probes')
                if fmt=='team2v2':
                    self.assertEqual({j['meta']['context'] for j in seen[0]},{'baseline_partner','self_team'})
                    self.assertEqual({j['meta']['context'] for j in seen[1]},{'baseline_partner','self_team'})

    def test_reduced_team_validation_does_not_weaken_formal_evaluation(self):
        from learning.sample import opening_map
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            jobs=evaluation_jobs('.', 'policy','baseline',['baseline'],1,19,3000000000,'unused',formats=['team2v2'],team_contexts=('baseline_partner',))
        results=[dict(id=j['id'],status='complete',result=dict(bots=j['bots'],teams=j['teams'],winning_team=j['teams'][j['meta']['policy_sides'][0]-1],faults={})) for j in jobs]
        self.assertEqual(comparisons(jobs,results,min_blocks=1,team_contexts=('baseline_partner',))['team2v2']['blocks'],1)
        self.assertEqual(comparisons(jobs,results,min_blocks=1)['team2v2']['missing_blocks'],1)
        with patch('learning.maps.frozen_map',return_value=(opening_map(4),'0'*64)):
            full=evaluation_jobs('.', 'policy','baseline',['baseline'],30,19,3000000000,'unused',formats=['team2v2'])
        self.assertEqual(len(full),240)
        validate_config(default_config())
        with self.assertRaises(ValueError):validate_config(default_config()|dict(validation_interval=0))


if __name__=='__main__':unittest.main()
