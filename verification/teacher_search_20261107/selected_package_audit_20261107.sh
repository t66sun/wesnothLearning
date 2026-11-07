set -eu
cd /home/tongshu/myDev/wesnothLearning/verification/teacher_search_20261107/sources/20261106T190845_35d8f04a582f
export PYTHONPATH="$PWD"
/home/tongshu/venv/bin/python - <<'PY'
from pathlib import Path
import zipfile,time
from learning.teacher_lab.packages import read,digest,write_new
root=Path('/home/tongshu/myDev/wesnothLearning/verification/teacher_search_20261107')
lab=root/'experiment_v2';post=lab/'selection'
selected=read(post/'selected.json');timer=read(lab/'clock.json');manifest=read(lab/'manifest.json')
assert digest(selected['package'])==selected['package_sha256']
assert digest(manifest['baseline']['package'])==manifest['baseline']['package_sha256']
assert selected['frozen']>=timer['exploration_end']
checked={}
with zipfile.ZipFile(selected['package']) as combined:
 for fmt,row in selected['source_candidates'].items():
  assert row['registered']<timer['exploration_end']
  assert digest(row['package'])==row['package_sha256']
  prefix='selected_teacher/lua/'+fmt+'/'
  with zipfile.ZipFile(row['package']) as original:
   source_prefix=row['name']+'/lua/'
   expected={name[len(source_prefix):]:original.read(name).decode().replace(
      '~add-ons/'+row['name']+'/lua/','~add-ons/selected_teacher/lua/'+fmt+'/')
      for name in original.namelist() if name.startswith(source_prefix) and name.endswith('.lua')}
   actual={name[len(prefix):]:combined.read(name).decode()
      for name in combined.namelist() if name.startswith(prefix) and name.endswith('.lua')}
   assert expected==actual,fmt
  checked[fmt]=dict(candidate=row['name'],files=len(actual),source_commit=row['source_commit'],
                    package_sha256=row['package_sha256'],parameters=row['parameters'],
                    effective_algorithm='beam' if fmt=='ffa4' and row['parameters']['algorithm']=='pvs' else row['parameters']['algorithm'],
                    offensive_resistance_capture='resistance_against(kind,true)' in actual.get('public.lua',''),
                    response_aware_beam='Score replies before pruning' in actual.get('search.lua',''))
design=read(post/'holdout_design.json');validation=read(post/'validation/plan.json')
holdout=read(post/'holdout/plan.json');scheduled=read(post/'holdout/schedule.json')
assert design['frozen']<=validation['created']<=selected['frozen']<=holdout['created']
expected={j['id']:j for rows in design['schedules'].values() for j in rows}
for job in expected.values():
 job['bots']=[selected['package'] if bot=='FROZEN_SELECTION' else bot for bot in job['bots']]
 job['meta']['policy']=selected['package']
assert len(expected)==len(scheduled) and expected=={j['id']:j for j in scheduled}
assert digest(lab/'clock.json')==read(root/'post_launcher.json')['clock_sha256']
audit=dict(passed=True,checked=time.time(),selected_sha256=selected['package_sha256'],formats=checked,
           evaluator_source=Path('SOURCE_COMMIT').read_text().strip(),
           holdout_design_sha256=digest(post/'holdout_design.json'),holdout_schedule_sha256=digest(post/'holdout/schedule.json'),
           timeline=dict(design_frozen=design['frozen'],validation_started=validation['created'],
                         selected_frozen=selected['frozen'],holdout_started=holdout['created']),
           assertion='Each selected strategy equals its original frozen Lua files after namespace relocation only.')
write_new(root/'selected_package_audit.json',audit)
print(audit)
PY
