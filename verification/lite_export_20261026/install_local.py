"""Install the reviewed local-trial package under the explicit user exception."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
DRAFT = ROOT / 'delivery/lite_final_20261026_draft'
ADDONS = Path('C:/Users/Toshu/OneDrive/文档/My Games/Wesnoth1.18/data/add-ons').resolve()
SOURCE = DRAFT / 'NeuralArena20261026'
TARGET = (ADDONS / SOURCE.name).resolve()
assert TARGET.parent == ADDONS and TARGET.name == 'NeuralArena20261026'
assert not TARGET.exists(), TARGET
manifest = json.loads((DRAFT / 'installation_manifest.json').read_text(encoding='utf-8'))
assert manifest['installation_allowed'] is False
assert manifest['audits']['ffa4']['status'] == 'not_passed'
assert manifest['audits']['ffa4']['python_lua_max_error'] > 1e-5

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for name, expected in manifest['files'].items():
    assert digest(SOURCE / name) == expected, name
for fmt, checkpoint in manifest['checkpoints'].items():
    assert digest(DRAFT / 'checkpoints' / (fmt + '.pt')) == checkpoint['checkpoint_sha256'], fmt
previous_directories = sorted(p.name for p in ADDONS.iterdir() if p.is_dir())
previous = {str(p):digest(p) for folder in ADDONS.glob('NeuralArena*') if folder.is_dir()
            for p in folder.rglob('*') if p.is_file()}
shutil.copytree(SOURCE, TARGET)
for name, expected in manifest['files'].items():
    assert digest(TARGET / name) == expected, name
trial = dict(status='explicit_local_trial_exception',
    authorization='允许本次本地试用例外安装，保留未通过标记',
    installed_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    numeric_gate_status='not_passed', numeric_gate_threshold=1e-5,
    ffa4_python_lua_max_error=manifest['audits']['ffa4']['python_lua_max_error'],
    source_revision=manifest['source_revision'], checkpoints=manifest['checkpoints'],
    evaluation=manifest['evaluation'], scope='local trial only; not accepted numerical parity or native strength',
    original_installation_manifest_sha256=digest(DRAFT / 'installation_manifest.json'))
(TARGET / 'LOCAL_TRIAL.json').write_text(json.dumps(trial, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert all(digest(Path(name)) == expected for name, expected in previous.items())
assert all((ADDONS / name).is_dir() for name in previous_directories)
output = EVIDENCE / 'installed-native-preprocess'
assert not output.exists(), output
command = ['D:/SteamLibrary/steamapps/common/wesnoth/wesnoth.exe', '--wnoconsole', '--no-log-to-file',
           '--preprocess-defines=MULTIPLAYER,SKIP_CORE', '--preprocess', str(TARGET / '_main.cfg'), str(output)]
result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
(EVIDENCE / 'installed-native-preprocess.local.log').write_text(json.dumps(command, ensure_ascii=False) + '\n'
    + result.stdout + '\n' + result.stderr + '\nEXIT ' + str(result.returncode) + '\n', encoding='utf-8')
assert result.returncode == 0, result.stderr
expanded = (output / '_main.cfg').read_text(encoding='utf-8')
assert 'arena_NeuralArena20261026' in expanded and '~add-ons/NeuralArena20261026/lua/bot.lua' in expanded
assert json.loads((TARGET / 'LOCAL_TRIAL.json').read_text(encoding='utf-8'))['numeric_gate_status'] == 'not_passed'
record = dict(installed=str(TARGET), original_files_verified=len(manifest['files']),
    additional_files=['LOCAL_TRIAL.json'], previous_directories=previous_directories,
    previous_model_files_verified_unchanged=len(previous), native_registration_exit=result.returncode,
    trial=trial, installed_files={str(p.relative_to(TARGET)):digest(p) for p in sorted(TARGET.rglob('*')) if p.is_file()})
(EVIDENCE / 'installation.local.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(installed=str(TARGET), original_files_verified=len(manifest['files']),
    previous_model_files_unchanged=len(previous), native_registration_exit=result.returncode,
    numeric_gate_status='not_passed', explicit_local_trial_exception=True), ensure_ascii=False, indent=2), flush=True)
