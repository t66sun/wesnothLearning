import json, pathlib, unittest, sys
from learning.common import sha256
root=pathlib.Path.cwd()
names=[
 'tests.v5.test_training_failure_fixes.FailureBoundaryTests.test_underfilled_promotion_never_selects_best',
 'tests.v5.test_training_failure_fixes.FailureBoundaryTests.test_internal_export_resume_keeps_weights_integrity_without_sdk_size_cap',
 'tests.v5.test_training_failure_fixes.PhaseEntryTests',
]
result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(unittest.defaultTestLoader.loadTestsFromNames(names))
assert result.wasSuccessful()
p=root/'verification/training_repair_20261023/stage_outputs_v2/summary.json'
data=json.loads(p.read_text())
for fmt,item in data.items():
 final=item['final']
 print('STAGE_RESULT',json.dumps(dict(format=fmt,methods=item['methods'],updates=item['updates'],
  optimizer_steps=item['optimizer_steps'],selected_version=final['version'],selected_kind=final['selected_kind'],
  pretraining_complete=final['pretraining_complete'],forced_ppo=final['forced_ppo'],
  controls=final['controls'],selected_sha256=item['selected_sha256'])),flush=True)
print('AFFECTED_NEW_CHECKS_PASS',result.testsRun,flush=True)
