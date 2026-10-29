"""Regressions for the v100 failure; no formal training or game collection."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from learning.common import read_json, write_json
from learning.experiment import opening_gate
from learning.reward_metrics import summarize_game
from learning.reward_metrics import METRICS_VERSION
from learning.features import ACTION, GLOBAL, ENTITY
from tests.test_lua_contracts import initialize
from tests import test_validation_cadence as cadence
from tests.v5.test_pipeline_contract import observation_row, result


class ReferencePlanningTests(unittest.TestCase):
    def runner(self, temp, fmt):
        from learning.schedule import evaluation_jobs
        from learning.rules_catalog import load, resolve_dir
        runner = cadence.ValidationCadenceTests().runner(temp, fmt)
        runner.config['engine'] = 'lite'
        rules = load(resolve_dir(runner.config['rules_dir']))['rules_version']
        jobs = evaluation_jobs(temp, 'student', 'gpt6astra.zip', ['gpt6astra.zip'],
                               12, 17, 3000000000, 'unused', formats=[fmt],
                               team_contexts=('astra_partner','self_team'))
        rows, batches = [], []
        def persist():
            (Path(temp)/'jobs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        def execute(proposals, name):
            batches.append(proposals)
            for j in proposals:
                meta, side = j['meta'], j['meta']['seat']
                d = dict(format=fmt, engine_id='lite', rules_version=rules,
                         metrics_version=METRICS_VERSION, map=meta['map'], map_sha256=meta['map_sha256'],
                         faction=j['factions'][side-1], context=meta['context'],
                         source='astra', teacher='gpt6astra', map_partition='validation',
                         game_family=j['game_family'], complete=True)
                rows.append(dict(id=j['id'], status='complete', meta=meta, reward_diagnostics=[d]))
            persist()
        runner.execute = execute
        return runner, jobs, rows, batches, persist

    def test_bounded_calls_reach_every_panel_stratum_without_reused_ids(self):
        for fmt, layers in (('duel',6),('ffa4',6),('team2v2',12)):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as temp:
                runner, jobs, rows, batches, _ = self.runner(temp, fmt)
                for version in range(10, 10+layers//3*10, 10):
                    runner.collect_reward_references(jobs, version)
                self.assertTrue(all(0 < len(b) <= 12 for b in batches))
                self.assertEqual(len(rows), layers*4)
                self.assertEqual(len({r['id'] for r in rows}), layers*4)
                self.assertEqual(len({r['reward_diagnostics'][0]['game_family'] for r in rows}), layers*4)
                runner.collect_reward_references(jobs, 100)
                self.assertEqual(len(rows), layers*4)

    def test_failed_slot_uses_new_attempt_not_success_count(self):
        with tempfile.TemporaryDirectory() as temp:
            runner, jobs, rows, batches, persist = self.runner(temp, 'ffa4')
            runner.collect_reward_references(jobs, 10)
            bad = rows[2]
            bad['reward_diagnostics'][0]['complete'] = False
            persist()
            previous = {r['id'] for r in rows}
            runner.collect_reward_references(jobs, 20)
            self.assertTrue(all(j['id'] not in previous for j in batches[-1]))
            prefix = bad['id'].rsplit('-',1)[0]
            self.assertIn(prefix+'-4', {j['id'] for j in batches[-1]})

    def test_metric_fault_freezes_adaptive_until_valid_metrics(self):
        from learning.control import RewardController
        with tempfile.TemporaryDirectory() as temp:
            c = RewardController(temp, 'duel', config=dict(mode='adaptive'))
            c.games = 100
            with patch.object(c, '_decision') as decision:
                c.boundary(50, dict(status='error',error='bad metric',validation_blocks=[]))
                c.boundary(100, dict(partition='train',new_games=4))
                decision.assert_not_called()
            restored = RewardController(temp,'duel',state=c.state_dict())
            self.assertEqual(restored.metrics_error, 'bad metric')
            with patch.object(restored,'_decision',return_value=({},'')) as decision:
                restored.boundary(101,dict(partition='validation',validation_blocks=[]))
                decision.assert_called_once()


class FailureBoundaryTests(unittest.TestCase):
    def test_underfilled_promotion_never_selects_best(self):
        with tempfile.TemporaryDirectory() as temp:
            runner=cadence.ValidationCadenceTests().runner(temp)
            runner.state['version']=100
            write_json(Path(temp)/'bc_gate.json',dict(imitation=dict(effective=False)))
            def execute(jobs,name):
                jobs=[j for j in jobs if j['meta']['block']==0]
                return jobs,[dict(id=j['id'],status='complete',result=dict(bots=j['bots'],winner=0,faults=[])) for j in jobs]
            runner.execute=execute
            runner.validate_model('bc')
            self.assertIsNone(runner.state.get('best_kind'))
            self.assertFalse((Path(temp)/'best.pt').exists())

    def test_internal_export_resume_keeps_weights_integrity_without_sdk_size_cap(self):
        from learning.experiment import FormatExperiment
        from learning.model import Policy
        import addons
        with tempfile.TemporaryDirectory() as temp:
            runner=cadence.ValidationCadenceTests().runner(temp)
            model=Policy('duel')
            addon=Path(FormatExperiment.ensure_export(runner,model,'support','LearningSupport'))
            # The actual generated weights exceed the submitted-package limit.
            with self.assertRaisesRegex(ValueError,'16 MiB'):
                addons.validate(addon)
            self.assertEqual(FormatExperiment.ensure_export(runner,model,'support','LearningSupport'),str(addon))
            with (addon/'lua/weights_duel.lua').open('a') as stream: stream.write('--changed\n')
            with self.assertRaisesRegex(ValueError,'weights differ'):
                FormatExperiment.ensure_export(runner,model,'support','LearningSupport')

    def test_training_error_is_failed_without_final_holdout(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = cadence.ValidationCadenceTests().runner(temp)
            runner.state.update(stage='bc', error=None)
            runner.learn = Mock(side_effect=RuntimeError('optimizer failed'))
            runner.final_evaluation = Mock()
            with self.assertRaisesRegex(RuntimeError, 'optimizer failed'):
                runner.run()
            runner.final_evaluation.assert_not_called()
            self.assertEqual(runner.state['stage'], 'failed')
            self.assertEqual(runner.state['failed_stage'], 'bc')
            self.assertIn('optimizer failed', runner.state['error'])
            summary = json.loads((Path(temp)/'report/summary.json').read_text())
            self.assertEqual(summary['status'], 'trainer_failed')
            # The trainer process owns the single traceback; a second copy in
            # errors.log only duplicated it.
            self.assertFalse((Path(temp)/'errors.log').exists())

    def test_v100_metric_error_keeps_opening_and_records_error(self):
        for fmt in ('duel', 'ffa4', 'team2v2'):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as temp:
                runner = cadence.ValidationCadenceTests().runner(temp, fmt)
                runner.state.update(version=100, pending_validation='bc')
                runner.controller.freeze = lambda: dict(mode='adaptive')
                runner.collect_reward_references = Mock()
                write_json(Path(temp)/'bc_gate.json', dict(imitation=dict(effective=True),
                    coverage=dict(passed=True), corpus=dict(passed=True),
                    distinct_scenarios=12, min_distinct=12, missing_scenario_rows=0))
                calls = []
                def execute(jobs, name):
                    calls.append(name)
                    if name.startswith('opening-'):
                        return jobs, [dict(status='complete', meta=j['meta'], behavior=[
                            dict(side=j['meta']['seat'], left_castle=True, village_captured=True,
                                 end_turn=True, usable_moves=0, remaining_moves=6)]) for j in jobs]
                    return jobs, []
                runner.execute = execute
                with patch('learning.reward_metrics.build_control_metrics', side_effect=KeyError('astra_coverage5')):
                    runner.validate_model('bc')
                runner.collect_reward_references.assert_called_once()
                self.assertIn('opening-000100', calls)
                self.assertIsNone(runner.state['pending_validation'])
                self.assertTrue(runner.state['effective'])
                metrics = read_json(Path(temp)/'validation/control-v000100.json')
                self.assertEqual(metrics['status'], 'error')
                self.assertEqual(metrics['validation_blocks'], [])
                self.assertIn('astra_coverage5', metrics['error'])


    def test_opening_probe_is_recorded_but_never_blocks_ppo(self):
        from unittest.mock import patch as patch_object
        with tempfile.TemporaryDirectory() as temp:
            runner=cadence.ValidationCadenceTests().runner(temp)
            runner.state.update(version=100,pending_validation='bc')
            runner.controller.freeze=lambda: dict(mode='adaptive')
            runner.collect_reward_references=Mock()
            write_json(Path(temp)/'bc_gate.json',dict(imitation=dict(effective=True),
                coverage=dict(passed=True),corpus=dict(passed=True),
                distinct_scenarios=12,min_distinct=12,missing_scenario_rows=0))
            def execute(jobs,name):
                if name.startswith('opening-'):
                    return jobs,[dict(status='complete',meta=j['meta'],behavior=[
                        dict(side=j['meta']['seat'],left_castle=False,village_captured=False,
                             end_turn=True,usable_moves=9,remaining_moves=1)]) for j in jobs]
                return jobs,[]
            runner.execute=execute
            with patch_object('learning.reward_metrics.build_control_metrics',
                              return_value=dict(partition='validation',validation_blocks=[],excluded_evidence=[])):
                runner.validate_model('bc')
            gate=read_json(Path(temp)/'bc_gate.json')
            self.assertTrue(runner.state['effective'])
            self.assertTrue(gate['passed'])
            self.assertFalse(gate['opening']['passed'])
            self.assertFalse(gate['opening']['blocking'])


class PhaseEntryTests(unittest.TestCase):
    def test_auto_uses_next_sampling_method_after_bc_gate(self):
        from learning.experiment import FormatExperiment
        for qualified in (False,True):
            with self.subTest(qualified=qualified), tempfile.TemporaryDirectory() as temp:
                runner=cadence.ValidationCadenceTests().runner(temp)
                runner.state.update(stage='bc',phase='auto',pending_validation='bc')
                runner.state['counters'].update(environment_games=0,collection_batches=0)
                def validated(method):
                    self.assertEqual(method,'bc')
                    runner.state.update(effective=qualified,pending_validation=None)
                runner.validate_model=validated
                runner.controller.boundary=lambda *args:None
                names=[]
                def execute(jobs,name):
                    names.append(name);runner.clock['update_deadline']=0
                    return [],[]
                runner.execute=execute
                with patch('learning.experiment.read_shards',return_value=[]):
                    runner.learn()
                self.assertEqual(names,[('ppo' if qualified else 'bc')+'-batch-000000'])

    def test_resumed_pending_batch_keeps_method_before_new_phase(self):
        from learning.phases import request_phase
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            runner=cadence.ValidationCadenceTests().runner(root/'duel')
            runner.state.update(stage='bc',phase='bc',error=None,pending_train=dict(method='bc'))
            runner.clock['update_deadline']=1
            runner.save()
            write_json(root/'manifest.json',dict(config=dict(formats=['duel'])))
            write_json(root/'clock.json',dict(update_deadline=1,deadline=2))
            request_phase(root,'ppo',force=True,reason='resume pending test',hours=1)
            seen=[]
            def finish():
                seen.append((runner.state['pending_train']['method'],runner.update_deadline()))
                runner.state.update(pending_train=None,phase_deadline=1)
                return True
            runner.finish_train=finish
            runner.run()
            self.assertEqual(seen[0][0],'bc')
            self.assertGreater(seen[0][1],1)
            self.assertEqual(runner.state['stage'],'ppo_complete')

    def test_forced_phase_is_explicit_preserves_gates_and_original_clock(self):
        from learning.phases import request_phase, apply_phase, show_phases
        import time
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            runner=cadence.ValidationCadenceTests().runner(root/'duel')
            runner.state.update(stage='bc',effective=False,phase='bc')
            runner.save()
            write_json(root/'manifest.json',dict(config=dict(formats=['duel'])))
            write_json(root/'clock.json',dict(update_deadline=1,deadline=2))
            with self.assertRaisesRegex(ValueError,'budget expired'):
                request_phase(root,'ppo',force=True,reason='requested')
            with self.assertRaisesRegex(ValueError,'BC gates'):
                request_phase(root,'ppo',hours=1)
            with self.assertRaisesRegex(ValueError,'reason'):
                request_phase(root,'ppo',force=True,hours=1)
            before=copy.deepcopy(runner.clock)
            request_phase(root,'ppo',force=True,reason='explicit test',hours=1)
            self.assertIsNotNone(show_phases(root)['duel']['pending'])
            apply_phase(runner)
            self.assertFalse(runner.state['effective'])
            self.assertEqual(runner.state['phase'],'ppo')
            self.assertEqual(runner.clock,before)
            self.assertGreater(runner.update_deadline(),time.time())
            self.assertEqual(runner.state['forced_ppo']['reason'],'explicit test')
            self.assertIsNone(show_phases(root)['duel']['pending'])

    def test_bc_only_stops_without_ppo_or_final_and_can_resume_as_ppo(self):
        from learning.phases import request_phase
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            runner=cadence.ValidationCadenceTests().runner(root/'duel')
            runner.state.update(stage='bc',effective=True,phase='bc',error=None)
            runner.final_evaluation=Mock()
            write_json(root/'manifest.json',dict(config=dict(formats=['duel'])))
            write_json(root/'clock.json',dict(update_deadline=3000000000,deadline=3000001000))
            runner.save()
            summary=runner.run()
            self.assertEqual(summary['status'],'stage_complete')
            self.assertEqual(runner.state['stage'],'bc_complete')
            runner.final_evaluation.assert_not_called()
            request_phase(root,'ppo')
            runner.learn=Mock(side_effect=lambda: runner.state.update(stage='ppo'))
            summary=runner.run()
            runner.learn.assert_called_once()
            self.assertEqual(summary['phase'],'ppo')

    def test_cli_phase_entry_is_separate_from_reward_controls(self):
        from learning.__main__ import parser
        args=parser().parse_args(['phase','ppo','--run-dir','runs/new','--force','--reason','user request','--hours','2'])
        self.assertEqual((args.command,args.phase,args.force,args.hours),('phase','ppo',True,2))
        self.assertEqual(parser().parse_args(['run','--phase','bc']).phase,'bc')


class OpeningAndFeatureTests(unittest.TestCase):
    def test_opponents_actions_cannot_pass_students_opening(self):
        opponent = dict(side=2, left_castle=True, village_captured=True,
                        end_turn=True, usable_moves=0, remaining_moves=0)
        student = dict(side=1, end_turn=True, usable_moves=15, remaining_moves=15)
        games = [dict(status='complete', meta=dict(seat=1), behavior=[opponent, student]) for _ in range(2)]
        self.assertFalse(opening_gate(games)['passed'])
        for game in games:
            game['behavior'].append(dict(side=1, left_castle=True, village_captured=True,
                                        end_turn=True, usable_moves=0, remaining_moves=6))
        self.assertTrue(opening_gate(games)['passed'])

    def test_repeated_move_uses_named_feature_not_primary(self):
        lua, modules = initialize()
        obs = modules['observation.lua'].capture(lua.table(), 1)
        actions, _ = modules['candidates.lua'].generate(obs, 200)
        action = next(a for _, a in actions.items() if a['kind'] == 'move')
        indices = {name: i+1 for i, (name, _) in enumerate(ACTION)}
        for repeated, primary in ((1, 0), (0, 1)):
            action['features'][indices['repeated_move']] = repeated
            action['features'][indices['move_primary']] = primary
            obs['memory']['repeated_moves'] = 0
            diagnostic = modules['candidates.lua'].diagnostics(obs, action)
            modules['candidates.lua'].remember(obs, action)
            self.assertEqual(diagnostic['repeated_move'], bool(repeated))
            self.assertEqual(obs['memory']['repeated_moves'], repeated)


class TerminalHorizonTests(unittest.TestCase):
    def test_real_lite_early_elimination_before_first_own_turn(self):
        from tests.v5 import test_pipeline_contract as pipeline
        from tests.v5 import helpers
        fixture=pipeline.LiteJobTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        units=[helpers._unit('p1','Fighter',1,3,2,leader=True,hp=1),
               helpers._unit('e1','Fighter',2,4,2,leader=True,hp=1)]
        spec=helpers.spec(units=units,max_turns=3,fog=False)
        for side in spec['sides']: side['gold']=0
        def choose(row):
            index=next((i for i,c in enumerate(row['candidates']) if c['kind']=='attack'),0)
            return dict(choice=index,log_probability=0.,value=0.)
        job=fixture.job(bots=['p','p'],game_spec=spec,policy=choose,bootstrap_policy=lambda row:0.)
        job['meta']['phase']='validation'
        with pipeline.catalog_patch(fixture.rules_dir):
            outcome=pipeline.play_lite_job(job)
        self.assertEqual(outcome['status'],'complete',outcome)
        self.assertEqual(outcome['result']['reason'],'victory')
        self.assertLess(outcome['result']['turns'],5)
        self.assertEqual(len(outcome['reward_diagnostics']),2)
        self.assertTrue(all(d['complete'] for d in outcome['reward_diagnostics']),outcome['reward_diagnostics'])
        loser=next(d for d in outcome['reward_diagnostics'] if d['side'] not in outcome['result']['survivors'])
        self.assertEqual(loser['leader_survival'],0)
        self.assertAlmostEqual(loser['loss'],1/40)
        rows=pipeline.read_gzip(job['shard'])
        self.assertTrue(all('metric_event' not in r for r in rows))

    def test_early_terminal_snapshot_preserves_real_winner_and_loser(self):
        for dead in (False, True):
            with self.subTest(dead=dead):
                rows = [observation_row(turn) for turn in range(1, 5)]
                snap = copy.deepcopy(observation_row(4))
                snap['metric_event'] = 'eliminated' if dead else 'terminal'
                if dead:
                    for name in ('own_units', 'own_hp', 'leader_hp_fraction'):
                        snap['global'][[n for n, _ in GLOBAL].index(name)] = 0
                    snap['spatial']['entities'] = []
                    snap['reward_raw']['control'] = 0
                outcome = result()
                outcome.update(reason='victory', turns=4, survivors=[2] if dead else [1])
                job = dict(id='short', engine='lite', factions=['Fighter','Skeleton'],
                           meta=dict(format='duel', map='m', map_sha256='h', map_partition='validation', context='solo'))
                d = summarize_game(rows, outcome, job, snapshots=[snap])[0]
                self.assertTrue(d['complete'], d['missing'])
                self.assertEqual(d['horizons']['10']['snapshot_turn'], 4)
                self.assertEqual(d['horizons']['10']['absorbing'], True)
                self.assertEqual(d['leader_survival'], 0 if dead else 1)
                self.assertEqual(d['control'], 0 if dead else .2)
                self.assertEqual(d['loss'], 1 if dead else 0)

    def test_budget_or_fault_is_not_a_terminal_observation(self):
        rows = [observation_row(turn) for turn in range(1, 4)]
        snap = dict(copy.deepcopy(rows[-1]), metric_event='terminal')
        for reason, faults in (('turn_limit', []), ('victory', ['broken'])):
            outcome = dict(result(), reason=reason, turns=3, faults=faults)
            d = summarize_game(rows, outcome, dict(id='bad'), snapshots=[snap])[0]
            self.assertFalse(d['complete'])


if __name__ == '__main__':
    unittest.main()
