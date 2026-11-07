"""Consumer routing uses frozen roles without changing the training design."""
import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from learning.experiment import FormatExperiment
from learning.schedule import teacher_jobs, rollout_jobs, evaluation_jobs, teacher_factions
from learning.teachers import roles
from learning.teachers.registry import freeze_set, execution_matrix, require_same_teachers
from learning.teachers.runtime import prepare_job
from learning.tasks import TASK_ID
from tests.v5.test_branch_teacher_evidence import result
from tests.v5.test_pipeline_contract import diagnostic, reference, evidence, validation_job, validation_result, strata_row, control_block


class TeacherRoleRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.contract=freeze_set(self.root/'teachers','mixed-20261107')

    def runner(self,fmt='duel',engine='lite'):
        from tests.test_validation_cadence import ValidationCadenceTests
        runner=ValidationCadenceTests().runner(self.root/fmt,fmt)
        runner.directory.mkdir(exist_ok=True)
        runner.config.update(engine=engine,task_id=TASK_ID)
        runner.manifest=dict(teacher_set=copy.deepcopy(self.contract),rules=dict(rules_sha256='frozen-rules'))
        runner.teachers=[roles.package(runner)]
        runner.native_fixed=roles.fixed(runner,'native');runner.fixed=roles.fixed(runner)
        return runner

    def bind(self,runner,job):
        job.update(engine=runner.config['engine'],task_id=TASK_ID)
        job['meta']['engine_id']=job['engine']
        roles.bind_job(runner,job)
        return prepare_job(job,job['engine'])

    def test_actual_roles_budgets_and_teacher_labels_for_six_cells(self):
        for fmt in self.contract['formats']:
            for engine in ('native','lite'):
                runner=self.runner(fmt,engine)
                spec=roles.descriptor(runner)
                jobs=teacher_jobs(self.root,[spec['package']],runner.fixed,'support',0,17,3e9,'unused',formats=[fmt],count=4)
                seen=set()
                for job in jobs:
                    job=self.bind(runner,job);side=str(job['meta']['seat']);seen.add(int(side))
                    self.assertEqual(job['learning']['sides'][side]['teacher_identity']['teacher_strategy'],spec['strategy'])
                    self.assertEqual(job['seat_timeouts'][side],dict(timeout=spec['timeout'],first_timeout=spec['first_timeout']))
                    self.assertEqual(job['timeout'],1)
                    self.assertEqual(job['meta']['reference_teacher'],roles.identity(runner,'reward_reference'))
                    self.assertEqual(job['max_turns'],30)
                    if engine=='lite':self.assertNotIn('baseline',job['bots'])
                    elif fmt=='team2v2':self.assertIn('baseline',job['bots'])
                self.assertEqual(seen,set(range(1,3 if fmt=='duel' else 5)))

    def test_ppo_pool_and_teammate_cycle_preserved(self):
        for fmt in self.contract['formats']:
            runner=self.runner(fmt,'native')
            jobs=rollout_jobs(self.root,'student',['history'],runner.fixed,'support',1,0,17,3e9,'unused',formats=[fmt])
            counts=Counter(item['role'] for j in jobs for item in j['meta']['composition'] if item['role']!='teammate')
            self.assertEqual(counts['fixed'],2*counts['history']);self.assertEqual(counts['current'],counts['history'])
            for job in jobs:
                job['learning']['dagger_teacher']=roles.package(runner)
                prepared=self.bind(runner,job)
                training=prepared['learning']['sides'][str(job['meta']['seat'])]
                self.assertEqual(training['dagger_entry'],roles.descriptor(runner)['entry'])
            if fmt=='team2v2':
                self.assertEqual([next(x['path'] for x in j['meta']['composition'] if x['role']=='teammate') for j in jobs],
                                 ['baseline',roles.package(runner,'opponent'),'student','student'])

    def test_teacher_faction_cycle_still_covers_six_factions_per_seat(self):
        import params
        for fmt in self.contract['formats']:
            n=2 if fmt=='duel' else 4
            seen={side:set() for side in range(1,n+1)}
            for i in range(120):
                side=(n-i%n)%n+1
                seen[side].add(teacher_factions(i,n,fmt)[side-1])
            self.assertTrue(all(values==set(params.FACTIONS) for values in seen.values()),seen)

    def test_evaluation_and_reference_read_their_own_roles(self):
        runner=self.runner('duel')
        astra=freeze_set(self.root/'astra','astra')['formats']['duel']['supervision']
        runner.manifest['teacher_set']['formats']['duel']['evaluation']=copy.deepcopy(astra)
        runner.manifest['teacher_set']['formats']['duel']['reward_reference']=copy.deepcopy(astra)
        self.assertNotEqual(roles.package(runner),roles.package(runner,'evaluation'))
        batches=[]
        runner.execute=lambda jobs,name:(batches.append(jobs) or jobs,[])
        runner.state['version']=10
        runner.validate_model('bc')
        self.assertEqual(batches[0][0]['meta']['control'],astra['package'])
        self.assertIn(astra['package'],batches[0][0]['bots'])
        runner.collect_reward_references(batches[0],10)
        for job in batches[1]:
            self.assertEqual(job['bots'][job['meta']['seat']-1],astra['package'])
            prepared=self.bind(runner,job)
            self.assertEqual(prepared['meta']['teacher'],'gpt6astra')
            self.assertEqual(prepared['learning']['sides'][str(job['meta']['seat'])]['teacher_identity']['teacher'],'gpt6astra')

    def test_quota_requires_current_teacher_complete_original_games(self):
        runner=self.runner()
        good=result('valid',meta=dict(roles.identity(runner),phase='teacher',engine_id='lite'))
        wrong=copy.deepcopy(good);wrong['id']='wrong';wrong['meta']['teacher_source_sha256']='old'
        dagger=copy.deepcopy(good);dagger['id']='dagger';dagger['meta']['phase']='ppo'
        runner.directory.joinpath('jobs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in (good,wrong,dagger)))
        self.assertEqual([r['id'] for r in runner.teacher_evidence()],['valid'])

    def test_backend_identity_change_requires_weights_only(self):
        manifest=dict(teacher_set=self.contract,teacher_executions=execution_matrix(self.contract))
        altered=copy.deepcopy(manifest)
        altered['teacher_executions']['duel']['supervision']['lite']['teacher_adapter_sha256']='changed'
        with self.assertRaisesRegex(ValueError,'weights-only'):require_same_teachers(manifest,altered,['duel'])
        require_same_teachers(manifest,manifest,['duel'])

    def test_modern_calibration_cannot_reuse_astra_or_other_task_backend_rules(self):
        from learning.reward_metrics import build_control_metrics
        runner=self.runner();identity=roles.identity(runner,'reward_reference')
        pinned=dict(source='teacher',reference_teacher=identity,task_id=TASK_ID,rules_sha256='rules',**identity)
        jobs=[validation_job('j'+str(i),rotation=i,reference_teacher=identity) for i in range(2)]
        for j in jobs:j.update(task_id=TASK_ID,rules_sha256='rules')
        results=[validation_result(j,[diagnostic(**pinned)]) for j in jobs]
        refs=[reference(str(i),**pinned) for i in range(4)]
        metrics=build_control_metrics(jobs,results,evidence(refs),{})
        self.assertEqual(len(metrics['validation_blocks']),1)
        block=metrics['validation_blocks'][0]
        self.assertEqual(block['strata'][0]['teacher_control'],.6)
        self.assertNotIn('astra_control',block['strata'][0])
        for key,value in [('task_id','other'),('rules_sha256','other'),('teacher_backend','native'),
                          ('teacher_package_sha256','other'),('teacher_adapter_sha256','other')]:
            changed=[dict(r,**{key:value}) for r in refs]
            self.assertEqual(build_control_metrics(jobs,results,evidence(changed),{})['validation_blocks'],[],key)
        old=[reference(str(i)) for i in range(4)]
        self.assertEqual(build_control_metrics(jobs,results,evidence(old),{})['validation_blocks'],[])

    def test_controller_equations_equal_with_new_reference_labels(self):
        from learning.control import RewardController
        old=control_block('x',strata=[strata_row()])
        modern=copy.deepcopy(old)
        modern['strata']=[{k.replace('astra_','teacher_'):v for k,v in row.items()} for row in old['strata']]
        self.assertEqual(RewardController._window([old]),RewardController._window([modern]))


if __name__=='__main__':unittest.main()
