"""Replay the frozen sampled learner rows for #359 without starting a game."""
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
import sys
import time

import torch

from learning.bc_anchor import weights_sha256
from learning.data import read_shards
from learning.export import load_model
from learning.model import batch
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import write_new

from review import verify_capture

KINDS = dict(end_turn='end_turn', recruit='recruit', move='movement',
             attack='combat', move_attack='combat')
STRATA = ('end_turn', 'recruit', 'movement', 'combat')


def band(turn):
    return '01-05' if turn <= 5 else '06-15' if turn <= 15 else '16-30'


def sample(job):
    rows = read_shards([job['shard']], format_name='duel', expected_task=TASK_ID)
    assert len(rows) >= 8 and all(r['game_id'] == job['id'] for r in rows)
    return [rows[i * (len(rows) - 1) // 7] for i in range(8)]


@torch.no_grad()
def logits_for(model, rows):
    cache = {}
    for i in range(0, len(rows), 16):
        part = rows[i:i + 16]
        logits, _ = model(*batch(part, dtype=torch.float64, history_cache=cache))
        yield from (x[:len(r['candidates'])] for r, x in zip(part, logits, strict=True))


def own_rows(model, jobs, samples):
    flat = [r for j in jobs for r in samples[j['id']]]
    groups, parity = defaultdict(list), []
    for row, logits in zip(flat, logits_for(model, flat), strict=True):
        probabilities = logits.softmax(-1)
        order = logits.topk(min(2, len(logits))).values
        choice, greedy = row['choice'], int(logits.argmax())
        logp = float(logits.log_softmax(-1)[choice])
        parity.append(abs(logp - row['log_probability']))
        strata = [KINDS[candidate['kind']] for candidate in row['candidates']]
        result = dict(entropy=float(torch.distributions.Categorical(logits=logits).entropy()),
                      top_two_logit_margin=float(order[0] - order[1]) if len(order) == 2 else None,
                      top_probability=float(probabilities[greedy]), sampled_differs=int(choice != greedy),
                      expected_differs=float(1 - probabilities[greedy]), turn=row['turn'],
                      decision=row['decision'], game=row['game_id'], candidates=len(logits),
                      sampled_type=strata[choice], greedy_type=strata[greedy],
                      action_mass={k: sum(float(v) for t, v in zip(strata, probabilities, strict=True) if t == k)
                                   for k in STRATA})
        groups['all', row['game_id']].append(result)
        groups[band(row['turn']), row['game_id']].append(result)
    assert max(parity) <= 1e-5
    return groups, max(parity)


def aggregate(groups):
    output = {}
    for stage in ('all', '01-05', '06-15', '16-30'):
        games = [x for (b, g), x in groups.items() if b == stage]
        if not games:
            continue
        keys = ('entropy', 'top_two_logit_margin', 'top_probability', 'sampled_differs', 'expected_differs')
        within = {k: [mean(r[k] for r in x if r[k] is not None)
                      for x in games if any(r[k] is not None for r in x)] for k in keys}
        tally = Counter(r['sampled_differs'] for x in games for r in x)
        kinds = {k: dict(sample_mass=mean(mean(r['action_mass'][k] for r in x) for x in games),
                         greedy_share=mean(mean(r['greedy_type'] == k for r in x) for x in games),
                         sampled_share=mean(mean(r['sampled_type'] == k for r in x) for x in games))
                 for k in STRATA}
        output[stage] = dict(games=len(games), rows=sum(tally.values()), disagreements=tally[1],
                             forced=sum(r['candidates'] == 1 for x in games for r in x),
                             mean={k: mean(v) if v else None for k, v in within.items()}, types=kinds)
    return output


def compare_greedy(model, rows, bc_greedy):
    games = defaultdict(list)
    for row, logits, best in zip(rows, logits_for(model, rows), bc_greedy, strict=True):
        for b in ('all', band(row['turn'])):
            games[b, row['game_id']].append(int(logits.argmax()) != best)
    return {b: dict(rows=sum(len(y) for (t, g), y in games.items() if t == b),
                    differences=sum(sum(y) for (t, g), y in games.items() if t == b),
                    equal_game_fraction=mean(mean(y) for (t, g), y in games.items() if t == b))
            for b, _ in games}


def main(capture, output):
    started = time.monotonic()
    manifest, jobs, _, _, archive = verify_capture(capture)
    samples = {j['id']: sample(j) for j in jobs}
    neutral = [r for j in jobs if j['meta']['role'] == 'bc' for r in samples[j['id']]]
    greedy, output_roles = None, {}
    for name, spec in manifest['roles'].items():
        model, _ = load_model(Path(spec['path']), 'duel')
        assert weights_sha256(model.state_dict()) == spec['weights_sha256']
        model.double().eval()
        own = [j for j in jobs if j['meta']['role'] == name]
        rows, parity = own_rows(model, own, samples)
        if name == 'bc':
            greedy = [int(x.argmax()) for x in logits_for(model, neutral)]
        output_roles[name] = dict(checkpoint=spec, own=aggregate(rows), logp_max_error=parity,
                                  same_v38_rows=compare_greedy(model, neutral, greedy),
                                  per_game={g: r for (b, g), r in rows.items() if b == 'all'})
        print(name, output_roles[name]['own']['all']['rows'], parity, flush=True)
    assert sum(x['own']['all']['rows'] for x in output_roles.values()) == 768
    write_new(output, dict(issue=359, source_capture=archive, strata=KINDS, roles=output_roles,
                           new_games=0, optimizer_updates=0, wall_seconds=time.monotonic() - started))


if __name__ == '__main__':
    torch.set_num_threads(1)
    main(*(Path(x).resolve() for x in sys.argv[1:]))
