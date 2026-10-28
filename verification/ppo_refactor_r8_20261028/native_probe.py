"""One five-turn stock duel with controlled entropy: off twice, then on.

LD_PRELOAD must point at deterministic_entropy.so, which freezes the native
default RNG that --rng-seed does not control. Without it the two capture-off
runs are not comparable and the gate fails closed.
"""
from pathlib import Path
import gzip
import json
import os
import sys
import time

from learning.common import ROOT, sha256, write_json
from learning.features import schema
from learning.manifest import teacher_identity
from learning.sample import play_job
from learning.stock_rca import frames_to_labels
import native

STABLE = ('bots', 'seed', 'turns', 'winner', 'survivors', 'reason', 'faults',
          'rank_points', 'eliminated', 'factions', 'spawns', 'rules_version')


def events(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def engine_events(frames):
    return [frame for frame in frames if frame['event'] != 'STOCK']


def digests(frames):
    import hashlib
    return hashlib.sha256(json.dumps(frames, sort_keys=True).encode()).hexdigest()


def run(destination, exe, support, teacher, name, enabled):
    learning = dict(support=str(support), sides={})
    if enabled:
        learning['stock_capture'] = [1, 2]
    job = dict(id=name, output=str(destination/(name+'.json')), bots=['baseline', 'baseline'],
               seed=20261028, factions=['Loyalists', 'Rebels'], max_turns=5, timeout=30,
               first_timeout=30, engine='native', wesnoth=exe, learning=learning,
               deadline=time.time()+300, teacher_identity=teacher)
    if enabled:
        job['shard'] = str(destination/'derived'/'capability.jsonl.gz')
    summary = play_job(job)
    write_json(destination/(name+'_summary.json'), summary)
    assert summary['status'] == 'complete', summary
    assert not summary['result']['faults'], summary
    observed = events(destination/(name+'.events.jsonl.gz'))
    assert not any(frame['event'] == 'LEARN' for frame in observed), 'stock controller emitted LEARN'
    return summary, observed


def main():
    destination = Path(sys.argv[1])
    destination.mkdir()  # Never overwrite a prior attempt.
    preload = os.environ.get('LD_PRELOAD', '')
    shim = Path(preload.split(':')[0]) if preload else None
    if not shim or not shim.is_file():
        write_json(destination/'probe.json', dict(fx1='control_missing',
                   reason='LD_PRELOAD deterministic entropy shim is required', ld_preload=preload))
        raise SystemExit('LD_PRELOAD deterministic entropy shim is required')
    exe = native.find_wesnoth(sys.argv[2])
    support = destination/'support'
    (support/'lua').mkdir(parents=True)
    for path in (ROOT/'lua').glob('*.lua'):
        (support/'lua'/path.name).write_text(path.read_text().replace('@ADDON@', 'LearningSupport'))
    (support/'lua/features.lua').write_text('return '+native.lua(schema()))
    (support/'lua/config.lua').write_text('return {candidate_budget_ms=200}')
    teacher = dict(teacher_identity('wesnoth_default_rca'), runtime_sha256=sha256(exe))
    summaries, observed = {}, {}
    for name, enabled in (('capture_off', False), ('capture_off_repeat', False), ('capture_on', True)):
        summaries[name], observed[name] = run(destination, exe, support, teacher, name, enabled)
    before, after = (summaries[key]['result'] for key in ('capture_off', 'capture_on'))
    assert {k: before[k] for k in STABLE} == {k: after[k] for k in STABLE}, 'RESULT changed'
    control = [engine_events(observed[key]) for key in ('capture_off', 'capture_off_repeat')]
    evidence = dict(shim=dict(path=str(shim), sha256=sha256(shim)),
                    off=digests(control[0]), off_repeat=digests(control[1]),
                    on=digests(engine_events(observed['capture_on'])))
    if control[0] != control[1]:
        write_json(destination/'probe.json', dict(fx1='control_nondeterministic',
                   reason='two capture-off runs with fixed entropy still differ',
                   stream=evidence, summaries={k: summaries[k]['result'] for k in summaries}))
        raise SystemExit('capture-off control is not deterministic')
    if control[0] != engine_events(observed['capture_on']):
        write_json(destination/'probe.json', dict(fx1='failed', reason='capture-on changed engine events',
                   stream=evidence, summaries={k: summaries[k]['result'] for k in summaries}))
        raise SystemExit('capture changed engine events')
    frames = [frame['data'] for frame in observed['capture_on'] if frame['event'] == 'STOCK']
    action_counts = {kind: sum(frame.get('type') == 'ACTION' and frame.get('kind') == kind
                               for frame in frames)
                     for kind in ('recruit', 'moveto', 'attack', 'recall', 'advance')}
    assert all(action_counts[k] > 0 for k in ('recruit', 'moveto', 'attack')), action_counts
    counts = summaries['capture_on']['stock_coverage']
    # Every watched engine action must have consumed its own fresh pre-action context.
    for kind, total in action_counts.items():
        seen = counts[kind]
        labelled = seen['matched'] + seen['ambiguous'] + seen['merged']
        assert labelled + seen['unmatched'] == total, (kind, seen, total)
        if total:
            assert seen['unmatched'] == 0, (kind, seen)
    assert counts['recruit']['matched'] > 0, counts
    assert counts['moveto']['matched'] + counts['moveto']['merged'] > 0, counts
    assert counts['attack']['matched'] + counts['attack']['ambiguous'] > 0, counts
    labels = []
    for side in (1, 2):
        rows, _ = frames_to_labels(frames, side=side, candidates_fn=lambda row: row['candidates'])
        labels.extend(rows)
    assert any(row['choice'] >= 0 for row in labels), 'no usable labels'
    observed_contexts = sum(1 for f in frames if f.get('type') == 'CONTEXT')
    invalid = sum(1 for f in frames if f.get('type') == 'INVALIDATE')
    after_errors = [f for f in frames if f.get('type') == 'AFTER_ERROR']
    assert not after_errors, after_errors
    probes = [f for f in frames if f.get('type') == 'CAPABILITIES']
    assert len(probes) == 2, probes
    hooks = [f for f in frames if f.get('type') == 'HOOK']
    assert len(hooks) == 6, hooks
    query = [f for f in hooks if f['name'] in ('teacher_turn', 'play_turn', 'take_turn') and f['callable']]
    report = dict(
        fx1='passed', fx2=counts, engine_actions=action_counts,
        contexts=dict(observed=observed_contexts, invalidated=invalid, labels=len(labels),
                      merged={kind: counts[kind]['merged']
                              for kind in ('recruit', 'moveto')},
                      exact=sum(row['choice'] >= 0 for row in labels)),
        fx3=dict(surface_probes=probes, hooks=hooks, turn_query_present=bool(query),
                 takeover='unsupported_with_stock_rca',
                 reason='1.18.8 exposes no per-turn query hook; a native per-decision Lua CA cannot '
                        'reach an out-of-process policy, so R9 keeps query=none and DAgger retired'),
        stream=evidence, identity=teacher, games=3, scenarios=1, max_turns=5,
        limits='Capability only; no strength, full coverage or training acceptance')
    write_json(destination/'probe.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
