"""Census retained-action disagreements on the existing #359 public probes."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

import torch

from actions import KINDS, STRATA, band, logits_for
from learning.common import sha256
from learning.data import advantages, read_shards
from learning.export import load_model
from learning.tasks import TASK_ID
from proof import archive_rows, fingerprint
from review import verify_capture
from verification.duel_ppo_comparison_20261106.audit import write_new

BANDS = ('01-05', '06-15', '16-30')
SEED = 'route-360-retained-20261115'
LIMIT = 2


def rank(probe):
    ident = f"{SEED}:{probe['game_id']}:{probe['decision']}"
    return hashlib.sha256(ident.encode()).hexdigest()


def model(checkpoint):
    assert sha256(Path(checkpoint['path'])) == checkpoint['checkpoint_sha256']
    m, _ = load_model(Path(checkpoint['path']), 'duel')
    return m.double().eval()


def prepare(base, output):
    m, jobs, _, _, capture = verify_capture(base)
    anchor = model(m['roles']['bc'])
    ppo = {name: model(spec) for name, spec in m['roles'].items() if name != 'bc'}
    strata = {(t, k): [] for t in BANDS for k in STRATA}
    totals = Counter()
    for job in jobs:
        meta = job['meta']
        role = meta['role']
        if role not in ppo:
            continue
        rows = read_shards([job['shard']], format_name='duel', expected_task=TASK_ID)
        a, _ = advantages(rows)
        ids = [i * (len(rows)-1) // 7 for i in range(8)]
        sample = [rows[i] for i in ids]
        archived = None
        for i, row, logits, base_logits in zip(ids, sample, logits_for(ppo[role], sample),
                                               logits_for(anchor, sample), strict=True):
            turn_band = band(row['turn'])
            totals[turn_band] += 1
            selected = row['choice']
            logged = float(logits.log_softmax(-1)[selected])
            assert abs(logged-row['log_probability']) <= 1e-5
            b, p = int(base_logits.argmax()), int(logits.argmax())
            if p != selected or p == b:
                continue
            if archived is None:
                archived = archive_rows(job)
                assert [r['decision'] for r in archived] == [r['decision'] for r in rows]
            original, alternate = row['candidates'][p], row['candidates'][b]
            k = KINDS[alternate['kind']]
            alt_probability, alt_reference = (float(x.softmax(-1)[b]) for x in (logits, base_logits))
            assert alt_probability > 0 and alt_reference > 0
            strata[turn_band, k].append(dict(
                game_id=job['id'], role=role, layout=meta['map'], side=row['side'], boundary=i,
                turn=row['turn'], decision=row['decision'], original_choice=p, alternative_choice=b,
                original_type=KINDS[original['kind']], alternative_type=k, turn_band=turn_band,
                public_sha256=fingerprint(archived[i]), observed_gae=a[i],
                ppo_probability_original=float(logits.softmax(-1)[p]), ppo_probability_alternative=alt_probability,
                bc_probability_alternative=alt_reference,
                ppo_alternative_minus_original_logit=float(logits[b]-logits[p])))
    chosen, seen, filled = [], set(), Counter()
    for _ in range(LIMIT):
        for key, choices in sorted(strata.items(), key=lambda item: (len(item[1]), item[0])):
            eligible = [r for r in choices if r['game_id'] not in seen]
            if eligible:
                row = min(eligible, key=rank)
                chosen.append(row)
                seen.add(row['game_id'])
                filled[key] += 1
    assert sum(totals.values()) == 576 and len(chosen) <= 24
    write_new(output, dict(scope='eight stratified rows from each of 72 archived PPO games',
                           snapshot_available_in_archive=False, omitted_opportunities='unobserved in archived retained rows',
                           capture_sha256=capture['archive_sha256'], selection_seed=SEED,
                           sampled_rows=totals, original_games=72,
                           eligible_original_games=len({r['game_id'] for cell in strata.values() for r in cell}),
                           games_started=0, optimizer_updates=0,
                           strata={'/'.join(k):dict(eligible_rows=len(v),eligible_games=len({r['game_id'] for r in v}),selected=filled[k])
                                   for k,v in strata.items()}, cases=chosen))
    print(json.dumps(dict(probes=sum(totals.values()), eligible=sum(map(len,strata.values())), selected=len(chosen),
                          case_roles=Counter(r['role'] for r in chosen),
                          case_maps=Counter(r['layout'] for r in chosen), output_sha256=sha256(output))))


if __name__ == '__main__':
    torch.set_num_threads(1)
    prepare(*(Path(x).resolve() for x in sys.argv[1:]))
