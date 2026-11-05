"""Read frozen run metadata; never load a trainer or modify run files."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def counts(items):
    return dict(sorted(Counter(items).items()))


def distribution(values):
    values = sorted(values)
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None,
                median=statistics.median(values) if values else None)


def inspect(root):
    result = {}
    for fmt in ('duel', 'ffa4', 'team2v2'):
        directory = root / fmt
        state = json.loads((directory / 'state.json').read_text())
        jobs = [json.loads(line) for line in (directory / 'jobs.jsonl').open()]
        complete = [j for j in jobs if j['status'] == 'complete']
        ppo = [h for h in state['history'] if h['method'] == 'ppo']
        by_phase = {}
        for phase in sorted({j.get('meta', {}).get('phase', 'other') for j in complete}):
            group = [j for j in complete if j.get('meta', {}).get('phase', 'other') == phase]
            factions = counts('|'.join(j['result'].get('factions', [])) for j in group)
            learner_factions = counts(j['result']['factions'][j['meta']['seat']-1]
                                      for j in group if j.get('meta', {}).get('seat'))
            by_phase[phase] = dict(games=len(group), reasons=counts(j['result'].get('reason', 'missing') for j in group),
                turns=distribution([j['result'].get('turns', 0) for j in group]),
                map_counts=counts(j.get('meta', {}).get('map', 'missing') for j in group),
                faction_rosters=factions, learner_factions=learner_factions,
                rows=sum((j.get('training_shard') or {}).get('written', 0) for j in group))
        schedules = []
        for path in sorted((directory / 'schedules').glob('ppo-batch-*.json')):
            schedules.extend(json.loads(path.read_text()))
        counter = Counter(j['scenario_family'] for j in schedules)
        scenario_designs = {}
        for job in schedules:
            scenario_designs.setdefault(job['scenario_family'], dict(map=job.get('meta', {}).get('map'),
                factions=job['factions'], max_turns=job['max_turns'], count=counter[job['scenario_family']]))
        by_opponent = {}
        for kind in ('fixed', 'history', 'current'):
            group = [j for j in complete if j.get('meta', {}).get('phase') == 'ppo'
                     and any(c.get('role') == kind for c in j['meta']['composition'])]
            wins = losses = draws = 0
            for job in group:
                r, seat = job['result'], job['meta']['seat']
                if r.get('teams'):
                    winning = r.get('winning_team')
                    if not winning: draws += 1
                    elif str(winning) == str(r['teams'][seat-1]): wins += 1
                    else: losses += 1
                else:
                    if not r.get('winner'): draws += 1
                    elif r['winner'] == seat: wins += 1
                    else: losses += 1
            by_opponent[kind] = dict(games=len(group),wins=wins,losses=losses,draws=draws)
        result[fmt] = dict(phases=by_phase, ppo_scenario_families=len(counter),
            ppo_scenarios=scenario_designs, opponent_results=by_opponent,
            ppo=dict(batches=len(ppo),kl_stops=sum(h['kl_stopped'] for h in ppo),
                     planned_steps=sum(h['planned_steps'] for h in ppo),
                     committed_steps=sum(h['committed_steps'] for h in ppo),
                     eligible_decisions=sum(h['eligible_decisions'] for h in ppo),
                     committed_decisions=sum(h['committed_decisions'] for h in ppo),
                     decisions_per_batch=distribution([h['eligible_decisions'] for h in ppo]),
                     windows_per_batch=distribution([h['sequence_windows'] for h in ppo]),
                     excluded_rehearsal_rows=distribution([h['rehearsal_rows_excluded'] for h in ppo]),
                     first_elapsed_hours=ppo[0]['elapsed_hours'] if ppo else None,
                     last_elapsed_hours=ppo[-1]['elapsed_hours'] if ppo else None,
                     rehearsal_sources=counts(s['source'] for h in ppo for s in h['rehearsal_sources'])))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(inspect(args.run), indent=2) + '\n')
