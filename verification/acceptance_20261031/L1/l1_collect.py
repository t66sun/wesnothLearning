"""Collect the L1 acceptance artifacts from a run tree into one evidence directory.

Usage: python l1_collect.py <src-root> <runs-root> <out-dir>
"""
import hashlib, json, shutil, sys
from pathlib import Path

src = Path(sys.argv[1]).resolve()
runs = Path(sys.argv[2]).resolve()
out = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def copy(relative, target, source=runs):
    source = Path(source) / relative
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return True
    return False


identities = dict(executable=str(src / '.runtime/install/bin/wesnoth'),
                  executable_sha256=sha256(src / '.runtime/install/bin/wesnoth'),
                  rules=(lambda catalog: dict(rules_file_sha256=catalog['rules_file_sha256'],
                                              complete=catalog['complete'],
                                              coverage=catalog['coverage_counts']))(
                      json.loads((src / 'data/rules/1.18.8/catalog.json').read_text())),
                  flags=json.loads((runs / 'a/manifest.json').read_text())['config'])
formats = {}
for name in ('a', 'b', 'c'):
    run = runs / name
    if not run.exists():
        continue
    state_path = run / 'duel/state.json'
    record = {}
    if state_path.exists():
        state = json.loads(state_path.read_text())
        history = state.get('history', [])
        record = dict(stage=state.get('stage'), status=state.get('status'),
                      version=state.get('version'), effective=state.get('effective'),
                      phase=state.get('phase'), phase_history=state.get('phase_history'),
                      forced_ppo=state.get('forced_ppo'), error=state.get('error'),
                      batches=[(row.get('batch'), row.get('method'), row.get('updates'),
                                row.get('policy_sha256_after')) for row in history],
                      applied_ppo=sum(1 for row in history
                                      if row.get('method') == 'ppo' and (row.get('updates') or 0) > 0),
                      kl_stops=[row for row in history if row.get('method') == 'ppo'
                                and (row.get('updates') or 0) == 0])
    jobs = run / 'duel/jobs.jsonl'
    if jobs.exists():
        rows = [json.loads(line) for line in jobs.read_text().splitlines() if line.strip()]
        record['jobs'] = dict(total=len(rows),
                              by_phase={},
                              by_status={})
        for row in rows:
            phase = (row.get('meta') or {}).get('phase', '?')
            record['jobs']['by_phase'][phase] = record['jobs']['by_phase'].get(phase, 0) + 1
            record['jobs']['by_status'][row.get('status', '?')] = record['jobs']['by_status'].get(row.get('status', '?'), 0) + 1
    for relative, target in (('manifest.json', f'{name}/manifest.json'),
                             ('clock.json', f'{name}/clock.json'),
                             ('branch.json', f'{name}/branch.json'),
                             ('boundary.json', f'{name}/boundary.json'),
                             ('duel/state.json', f'{name}/duel-state.json'),
                             ('duel/bc_gate.json', f'{name}/duel-bc_gate.json'),
                             ('duel/selection.json', f'{name}/duel-selection.json'),
                             ('duel/report/summary.json', f'{name}/duel-summary.json'),
                             ('duel/jobs.jsonl', f'{name}/duel-jobs.jsonl')):
        if copy(f'{name}/{relative}', out / target):
            record.setdefault('copied', []).append(str(target))
    for extra in ('timeline.log', 'same_future.json'):
        if copy(extra, out / extra):
            record.setdefault('copied', []).append(extra)
    for checkpoint in ('duel/selected.pt', 'duel/latest.pt', 'duel/last_ppo.pt'):
        if (run / checkpoint).exists():
            record.setdefault('checkpoints', {})[checkpoint] = sha256(run / checkpoint)
    formats[name] = record

(out / 'identities.json').write_text(json.dumps(dict(host=identities, runs=formats), indent=1,
                                                sort_keys=True) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({name: dict(stage=record.get('stage'), applied_ppo=record.get('applied_ppo'),
                             jobs=record.get('jobs'))
                  for name, record in formats.items()}, indent=1, sort_keys=True))
