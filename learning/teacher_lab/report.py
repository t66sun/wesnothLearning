from collections import Counter, defaultdict
from statistics import mean
from .packages import read, write_new
from .panels import GAMES_PER_BLOCK, HORIZONS
from learning.evaluate import bootstrap, official_score
from learning.formats import FORMATS


def score(result, side, horizon):
    if result.get('faults'):
        raise ValueError('faulted games are not normal wins or draws')
    if horizon == 30:
        return official_score(result, side) / (1 if len(result['bots'])>2 and not result.get('teams') else 3)
    if horizon != 100:
        raise ValueError('teacher experiment supports only 30/100-turn objectives')
    teams = result.get('teams')
    if teams:
        team = teams[side-1]
        winner = result['winning_team']
        if winner:
            return float(team == winner)
        return .5 if result['reason']=='turn_limit' and any(teams[s-1]==team for s in result['survivors']) else 0.
    if result.get('winner'):
        return float(result['winner']==side)
    return .5 if result['reason']=='turn_limit' and side in result['survivors'] else 0.


def valid(row):
    return (row is not None and row.get('status')=='complete' and not row['result'].get('faults')
            and not row.get('timing', {}).get('overruns'))


def compare(jobs, results, *, min_distinct=1):
    lookup = {r['id']: r for r in results}
    if len(lookup) != len(results):
        raise ValueError('duplicate result ids')
    cells = defaultdict(list)
    for job in jobs:
        m = job['meta']
        cells[(m['candidate'], m['opponent'], m['format'], m['horizon'])].append(job)
    summary = {}
    for (candidate, opponent, fmt, horizon), planned in cells.items():
        groups = defaultdict(list)
        for job in planned:
            groups[(job['meta'].get('panel', ''), job['meta']['block'])].append(job)
        clusters = defaultdict(list)
        completed_blocks = 0
        for group in groups.values():
            expected = GAMES_PER_BLOCK[fmt]
            contexts = ('baseline_partner', 'self_team') if fmt=='team2v2' else ('solo',)
            rotations = 2 if fmt=='duel' else 4
            design = {(j['meta']['context'], j['meta']['rotation']) for j in group}
            if (len(group)!=expected or design!={(c,r) for c in contexts for r in range(rotations)}
                    or not all(valid(lookup.get(j['id'])) for j in group)):
                continue
            differences = []
            for job in group:
                result = lookup[job['id']]['result'];m=job['meta']
                differences.append(mean(score(result, s, horizon) for s in m['policy_sides']) -
                                   mean(score(result, s, horizon) for s in m['control_sides']))
            family = tuple(sorted({j['scenario_family'] for j in group}))
            clusters[family].append(mean(differences));completed_blocks += 1
        observations = [lookup[j['id']] for j in planned if j['id'] in lookup]
        good = [j for j in planned if valid(lookup.get(j['id']))]
        fault_games = sum(bool(r.get('result', {}).get('faults')) or bool(r.get('timing', {}).get('overruns')) for r in observations)
        values = [mean(v) for v in clusters.values()]
        interval = bootstrap(values) if values else None
        complete = (len(observations)==len(planned) and completed_blocks==len(groups)
                    and len(clusters)>=min_distinct and fault_games==0)
        difference = mean(values) if values else None
        decisions = sum(lookup[j['id']].get('timing', {}).get('decisions', 0) for j in good)
        elapsed = sum((lookup[j['id']].get('timing', {}).get('mean_ms') or 0)*
                      lookup[j['id']].get('timing', {}).get('decisions', 0) for j in good)
        natural_wins = [mean(score(lookup[j['id']]['result'], side, 100)==1 for side in j['meta']['policy_sides'])
                        if lookup[j['id']]['result']['reason'] in ('last_leader','last_team') else 0 for j in good]
        row = dict(candidate=candidate, opponent=opponent, format=fmt, horizon=horizon,
                   planned=len(planned), observed=len(observations), statuses=dict(Counter(r['status'] for r in observations)),
                   blocks=completed_blocks, planned_blocks=len(groups), distinct_scenarios=len(clusters),
                   difference=difference, interval95=interval, complete=complete, fault_games=fault_games,
                   reasons=dict(Counter(lookup[j['id']]['result']['reason'] for j in good)),
                   natural_win_rate=mean(natural_wins) if natural_wins else None,
                   cap_rate=mean(lookup[j['id']]['result']['reason']=='turn_limit' for j in good) if good else None,
                   elimination_rate=mean(mean(s not in lookup[j['id']]['result']['survivors']
                                              for s in j['meta']['policy_sides']) for j in good) if good else None,
                   mean_action_ms=elapsed/decisions if decisions else None,
                   passed=bool(complete and difference>=.10 and interval[0]>0))
        summary['|'.join(map(str,(candidate,opponent,fmt,horizon)))] = row
    return summary


def candidate_cells(summary, name, opponent):
    return {(row['format'], row['horizon']): row for row in summary.values()
            if row['candidate']==name and row['opponent']==opponent}


def rank_key(cells, fmt):
    rows = [cells.get((fmt,h)) for h in HORIZONS]
    if any(not row or row['difference'] is None or row['fault_games'] or
           row['statuses'].get('infrastructure_error',0) for row in rows):
        return None
    gains = [row['difference'] for row in rows]
    times = [row['mean_action_ms'] for row in rows if row['mean_action_ms'] is not None]
    return min(gains), mean(gains), -mean(times) if times else 0


def provisional(cells):
    rows = [cells.get((fmt,h)) for fmt in FORMATS for h in HORIZONS]
    return (all(row and row['complete'] and row['blocks']>=3 and row['distinct_scenarios']>=3
                and row['difference']>=0 for row in rows) and mean(row['difference'] for row in rows)>0)


def load_panels(directory, *, partition='train', opponent=None):
    jobs, results = [], []
    for panel in sorted((directory / 'panels').glob('*')):
        if not (panel / 'results.json').exists():
            continue
        plan = read(panel / 'plan.json')
        if plan['metadata'].get('preflight') or plan['metadata'].get('partition')!=partition:
            continue
        schedule = read(panel / 'schedule.json')
        if opponent:
            schedule = [j for j in schedule if j['meta']['opponent']==opponent]
        ids = {j['id'] for j in schedule}
        jobs.extend(schedule)
        results.extend(r for r in read(panel / 'results.json') if r['id'] in ids)
    return jobs, results


def report_panel(directory, jobs, results, min_distinct=1):
    summary = compare(jobs, results, min_distinct=min_distinct)
    write_new(directory / 'summary.json', summary)
    return summary
