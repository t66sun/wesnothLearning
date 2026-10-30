"""R3 acceptance: frozen vs adapted Astra, one existing rotation block per format, native engine.

Usage: python r3_astra.py <repo-root> <output-dir> <wesnoth-binary>
"""
import json, os, shutil, subprocess, sys, tempfile, time, zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
final = Path(sys.argv[2]).resolve()
arbeit = root / 'runs/r3-20261031'
wesnoth = str(Path(sys.argv[3]).resolve())
final.mkdir(parents=True, exist_ok=True)
arbeit.mkdir(parents=True, exist_ok=True)
out = arbeit
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ['WESNOTH_EXE'] = wesnoth

from learning.common import ROOT, write_json, read_json, sha256
from learning.maps import decorate  # noqa: F401  (path side effects)
from learning.schedule import evaluation_jobs
from learning import evaluate, teachers
import addons, native


def stage(source, name):
    work = Path(tempfile.mkdtemp(prefix=name + '-')) / name
    shutil.copytree(source, work)
    for filename, text in zip(('_main.cfg', 'ai.cfg'), addons.configuration(name)):
        (work / filename).write_text(text, encoding='utf-8')
    write_json(work / 'arena.json', dict(schema=2, id=name, entry='lua/bot.lua'))
    for lua in (work / 'lua').glob('*.lua'):
        text = lua.read_text(encoding='utf-8')
        for old in ('gpt6astra',):
            text = text.replace(f'~add-ons/{old}/', f'~add-ons/{name}/')
        lua.write_text(text, encoding='utf-8')
    target = out / f'{name}.zip'
    addons.pack(work, target)
    return target


def unzip_frozen(package):
    target = Path(tempfile.mkdtemp(prefix='frozen-'))
    with zipfile.ZipFile(package) as archive:
        archive.extractall(target)
    members = list(target.iterdir())
    return members[0] if len(members) == 1 else target


def identities(frozen, adapted):
    rules = ROOT / 'data/rules/1.18.8'
    return dict(
        engine='native', wesnoth_version=subprocess.run([wesnoth, '--simple-version'],
                                                        capture_output=True, text=True).stdout.strip(),
        executable_sha256=sha256(wesnoth),
        rules_version='wesnoth-1.18.8-native-v2',
        rules_dir=str(rules),
        rules_sha256=sha256(rules / 'rules.json'),
        catalog_sha256=sha256(rules / 'catalog.json'),
        frozen_package_sha256=sha256(ROOT / 'data/opponents/gpt6astra.zip'),
        frozen_staged_sha256=sha256(frozen),
        adapted_source_sha256=teachers.source_digest(),
        adapted_parent_sha256=teachers.parent_digest(),
        adapted_profile=teachers.PROFILE,
        adapted_staged_sha256=sha256(adapted),
        adaptation_identity=teachers.identity(),
    )


def main():
    frozen = stage(unzip_frozen(ROOT / 'data/opponents/gpt6astra.zip'), 'astra_frozen')
    adapted = stage(ROOT / 'learning/teachers/gpt6astra', 'astra_adapted')
    table = identities(frozen, adapted)
    write_json(out / 'identities.json', table)
    print('identities', json.dumps(table, sort_keys=True), flush=True)
    exe = native.find_wesnoth(wesnoth)
    deadline = time.time() + 3600.
    summary = {}
    for index, fmt in enumerate(('duel', 'ffa4', 'team2v2')):
        jobs = evaluation_jobs(str(out), str(adapted), str(frozen), ['baseline'], 1,
                               20261017 + index, deadline, exe, label='r3-smoke',
                               formats=[fmt], min_distinct=1)
        write_json(out / f'schedule-{fmt}.json', jobs)
        print(f'{fmt}: {len(jobs)} games', flush=True)
        result = subprocess.run([sys.executable, '-m', 'learning', 'evaluate',
                                 '--jobs', str(out / f'schedule-{fmt}.json'), '--format', fmt,
                                 '--engine', 'native', '--workers', '8',
                                 '--output', str(out / fmt)],
                                cwd=str(root), capture_output=True, text=True)
        print(fmt, 'evaluate rc', result.returncode, result.stdout.strip()[-400:],
              result.stderr.strip()[-800:], flush=True)
        results = read_json(out / fmt / 'results.json')
        summary[fmt] = dict(rc=result.returncode,
                            comparison=evaluate.comparisons(jobs, results, min_blocks=1, min_distinct=1),
                            games=len(jobs))
    write_json(out / 'summary.json', summary)
    for name in ('identities.json', 'summary.json', 'astra_frozen.zip', 'astra_adapted.zip'):
        shutil.copy2(out / name, final / name)
    for path in sorted(out.glob('schedule-*.json')):
        shutil.copy2(path, final / path.name)
    print(json.dumps(summary, indent=1, sort_keys=True)[:4000], flush=True)


main()
