"""One five-turn stock duel, capture on/off. No trainer or corpus import."""
from pathlib import Path
import gzip
import json
import sys
import time

from learning.common import ROOT, sha256, write_json
from learning.features import schema
from learning.manifest import teacher_identity
from learning.sample import play_job
from learning.stock_rca import frames_to_labels
import native


def events(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def main():
    destination = Path(sys.argv[1])
    destination.mkdir()  # Never overwrite a prior attempt.
    exe = native.find_wesnoth(sys.argv[2])
    support = destination/'support'
    (support/'lua').mkdir(parents=True)
    for path in (ROOT/'lua').glob('*.lua'):
        (support/'lua'/path.name).write_text(path.read_text().replace('@ADDON@', 'LearningSupport'))
    (support/'lua/features.lua').write_text('return '+native.lua(schema()))
    (support/'lua/config.lua').write_text('return {candidate_budget_ms=200}')
    teacher = dict(teacher_identity('wesnoth_default_rca'),runtime_sha256=sha256(exe))
    summaries, observed = {}, {}
    for enabled in (False, True):
        name = 'capture_on' if enabled else 'capture_off'
        learning = dict(support=str(support), sides={})
        if enabled:
            learning['stock_capture'] = [1, 2]
        job = dict(id=name,output=str(destination/(name+'.json')),bots=['baseline','baseline'],
                   seed=20261028,factions=['Loyalists','Rebels'],max_turns=5,timeout=30,first_timeout=30,
                   engine='native',wesnoth=exe,learning=learning,deadline=time.time()+300,
                   teacher_identity=teacher)
        if enabled:
            job['shard'] = str(destination/'derived'/ 'capability.jsonl.gz')
        summaries[name] = play_job(job)
        write_json(destination/(name+'_summary.json'), summaries[name])
        assert summaries[name]['status']=='complete',summaries[name]
        assert not summaries[name]['result']['faults'],summaries[name]
        observed[name] = events(destination/(name+'.events.jsonl.gz'))
        assert not any(e['event']=='LEARN' for e in observed[name]),'stock controller emitted LEARN'
    stable = ('bots','seed','turns','winner','survivors','reason','faults','rank_points','eliminated','factions','spawns','rules_version')
    before, after = (summaries[key]['result'] for key in ('capture_off','capture_on'))
    assert {k:before[k] for k in stable}=={k:after[k] for k in stable},'RESULT changed'
    for kind in ('TURN','TURN_END','SNAPSHOT'):
        off = [e['data'] for e in observed['capture_off'] if e['event']==kind]
        on = [e['data'] for e in observed['capture_on'] if e['event']==kind]
        assert off==on,kind+' changed'
    frames = [e['data'] for e in observed['capture_on'] if e['event']=='STOCK']
    action_counts = {kind:sum(f.get('type')=='ACTION' and f['kind']==kind for f in frames)
                     for kind in ('recruit','moveto','attack','recall','advance')}
    assert all(action_counts[k]>0 for k in ('recruit','moveto','attack')),action_counts
    counts = summaries['capture_on']['stock_coverage']
    assert sum(sum(c.values()) for c in counts.values())==sum(action_counts.values())
    # This is the same FX1 input, not an extra scenario or trajectory.
    labels = []
    for side in (1,2):
        rows, _ = frames_to_labels(frames,side=side,candidates_fn=lambda row: row['candidates'])
        labels.extend(rows)
    assert any(row['choice']>=0 for row in labels),'no usable labels'
    probes = [f for f in frames if f.get('type')=='CAPABILITIES']
    assert len(probes)==2,probes
    query = any(p['teacher_turn'] for p in probes)
    report = dict(fx1='passed',fx2=counts,engine_actions=action_counts,
                  fx3=dict(surface_probes=probes,turn_query_present=query,
                           takeover='NOT RUN: no supported takeover adapter proven',
                           dagger_status='unsupported_with_stock_rca'),
                  identity=teacher,games=2,scenarios=1,max_turns=5,
                  limits='Capability only; no strength, full coverage or training acceptance')
    write_json(destination/'probe.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
