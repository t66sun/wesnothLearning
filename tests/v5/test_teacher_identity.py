"""Stock teacher identity is explicit; baseline jobs never become addon jobs."""
import unittest


class TeacherIdentityTests(unittest.TestCase):
    def test_lite_student_design_has_no_external_teacher_or_module(self):
        from learning.schedule import rollout_jobs
        from learning.lite_host import host_modules

        jobs=rollout_jobs('.', 'student',['history'],[],'support','v1',0,19,1000,'unused')
        self.assertEqual(len(jobs),12)
        self.assertTrue(all(set(job['bots'])<={'student','history'} for job in jobs))
        self.assertFalse(any(name.startswith('astra/') for name in host_modules()))
        self.assertTrue(any(name.startswith('astra/') for name in host_modules('gpt6astra')))

    def test_stock_label_identity_is_native_and_cannot_mix_with_astra(self):
        from types import SimpleNamespace
        from learning.data import validate_record
        from learning.manifest import teacher_identity
        from learning.updates import prepare
        from tests.v5 import helpers

        legacy=helpers.synthetic_decision_row(game_id='b',game_family='b')
        legacy['split']='train'
        identity=teacher_identity('wesnoth_default_rca')
        identity.update(rules_sha256='synthetic-v5',capture_sha256='0'*64,runtime_sha256='1'*64)
        stock=dict(legacy,source='stock_rca',teacher='wesnoth_default_rca',teacher_identity=identity,
            engine='native',engine_id='native',engine_version='1.18.8',native_version='1.18.8',
            rng_version='native-1.18.8',combat_version='native-1.18.8',teacher_profile='native',
            teacher_source_sha256='1'*64)
        validate_record(stock)
        with self.assertRaisesRegex(ValueError,'mixes teacher identities'):
            prepare(SimpleNamespace(format_name='duel'),[stock,legacy])
        with self.assertRaisesRegex(ValueError,'stock teacher is native-only'):
            validate_record(dict(stock,engine_id='lite'))

    def test_stock_teacher_cannot_be_queried_or_hosted_by_lite(self):
        from learning.manifest import teacher_identity
        from learning.schedule import teacher_jobs
        from learning.lite_host import play_lite_job

        teacher=teacher_identity('wesnoth_default_rca')
        with self.assertRaisesRegex(ValueError,'no query capability'):
            teacher_jobs('.', [teacher],['baseline'],'support',0,19,1000,'unused',formats=['duel'])
        result=play_lite_job(dict(id='stock-request',teacher_identity=teacher,
            learning=dict(sides={'1':dict(teacher='wesnoth_default_rca')}),bots=['student','student']))
        self.assertEqual(result['status'],'infrastructure_error')
        self.assertIn('stock RCA teacher is native-only',result['error'])

    def test_runner_uses_only_stock_native_reference_roles(self):
        from unittest.mock import patch
        from learning.experiment import FormatExperiment,default_config
        from learning.manifest import freeze
        from tests.v5 import helpers

        with helpers.temporary_directory() as directory:
            runtime=directory/'runtime-reference'
            runtime.write_bytes(b'unit-test runtime reference; never executed')
            with patch('learning.manifest.native.find_wesnoth',return_value=str(runtime)), \
                 patch('learning.manifest.dependency_versions',return_value=dict(packages=dict(torch='2.9.1+cpu'))):
                manifest,_=freeze(directory/'run',directory/'unused',None,default_config('cpu',engine='native'))
            with patch.object(FormatExperiment,'ensure_export',return_value='policy'):
                runner=FormatExperiment(directory/'run/duel','duel',manifest,
                    dict(started=0,update_deadline=3000000000.,deadline=3000000001.),lambda jobs,log:None)
            self.assertEqual(runner.reference_opponents,['baseline'])
            self.assertEqual(runner.fixed,['baseline'])
            self.assertEqual(runner.identity()['teacher'],'wesnoth_default_rca')
            from tests.v5.test_ppo_plan import _bc
            runner.state['pending_train']=dict(method='bc',paths=[],cursor={})
            with patch('learning.experiment.read_shards',return_value=_bc()), \
                 self.assertRaisesRegex(ValueError,'labels differ from the active teacher'):
                runner.finish_train()

    def test_stock_manifest_freezes_without_an_astra_package(self):
        from pathlib import Path
        from unittest.mock import patch
        from learning.experiment import default_config
        from learning.manifest import freeze,verify_frozen
        from tests.v5 import helpers

        with helpers.temporary_directory() as directory:
            runtime=directory/'runtime-reference'
            runtime.write_bytes(b'unit-test runtime reference; never executed')
            opponents=directory/'empty-opponents'
            opponents.mkdir()
            with patch('learning.manifest.native.find_wesnoth',return_value=str(runtime)), \
                 patch('learning.manifest.dependency_versions',return_value=dict(packages=dict(torch='2.9.1+cpu'))):
                manifest,teachers=freeze(directory/'run',opponents,None,default_config('cpu',engine='native'))
            self.assertEqual(manifest['teacher']['kind'],'wesnoth_default_rca')
            self.assertEqual(manifest['teacher']['version'],'1.18.8')
            self.assertEqual(manifest['teacher']['query'],'none')
            self.assertEqual(manifest['teacher']['action_source'],'engine_events')
            self.assertEqual(manifest['opponents'],[])
            self.assertEqual(teachers,['baseline'])
            verify_frozen(manifest)
            self.assertFalse(any(Path(directory/'run/frozen').rglob('*astra*')))

    def test_baseline_is_never_substituted(self):
        from learning.experiment import FormatExperiment
        from tests.test_validation_cadence import ValidationCadenceTests
        from tests.v5 import helpers

        with helpers.temporary_directory() as directory:
            runner=ValidationCadenceTests().runner(directory)
            runner.config['engine']='lite'
            runner.collector=lambda jobs,log:None
            job=dict(id='baseline-probe',bots=['student','baseline'],seed=19,
                     factions=['Drakes','Loyalists'],deadline=1000,meta=dict(format='duel'))
            jobs,_=FormatExperiment.execute(runner,[job],'baseline-probe')
            self.assertEqual(jobs[0]['bots'],['student','baseline'])


if __name__=='__main__':
    unittest.main()
