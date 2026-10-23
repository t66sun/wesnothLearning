import json, pathlib, subprocess, sys, unittest
import _engine_lite
out=pathlib.Path('verification/training_repair_20261023')
out.mkdir(parents=True,exist_ok=True)
print('ENV',sys.executable,_engine_lite.__file__,flush=True)
print('ACTIVE_TRAINING',subprocess.run(['pgrep','-af','python.*learning.*run'],capture_output=True,text=True).stdout,flush=True)
names=[
 'tests.v5.test_training_failure_fixes',
 'tests.v5.test_tactical_inputs',
 'tests.v5.test_pipeline_contract.RewardMetricsTests',
 'tests.v5.test_pipeline_contract.BoundaryTests',
 'tests.v5.test_pipeline_contract.LiteJobTests',
 'tests.v5.test_pipeline_contract.ConfigScheduleTests.test_opening_gate_needs_two_complete_games',
 'tests.v5.test_lite_default',
 'tests.test_validation_cadence',
 'tests.test_training_revision',
 'tests.test_experiment.ExperimentTests.test_resume_and_format_isolation',
]
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(suite)
(out/'unit_summary.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors)),indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
