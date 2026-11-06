"""Measure schedule construction only; no game, collection or optimizer is run."""
import argparse
from collections import Counter
import json
from math import perm
from pathlib import Path
import time

from learning.common import ROOT
from learning.features import schema
from learning.formats import FORMATS, PLAYERS
from learning.maps import SPLITS, scenario_identity
from learning.rollout_scenarios import _eligible_rosters
from learning.schedule import rollout_jobs
import params


def cycle(fmt):
    count = PLAYERS[fmt] * len(params.FACTIONS) * 2 * len(SPLITS[fmt]['train'])
    return [job for batch in range(count//4)
            for job in rollout_jobs(ROOT, 'student', ['history'], ['gpt6astra.zip'],
                                    'support', 'v1', batch, 19, 1000, 'unused', formats=[fmt])]


def measure(fmt):
    _eligible_rosters.cache_clear()
    wall, cpu = time.perf_counter(), time.process_time()
    cold = cycle(fmt)
    cold_wall, cold_cpu = time.perf_counter()-wall, time.process_time()-cpu
    cold_cache = _eligible_rosters.cache_info()._asdict()
    wall, cpu = time.perf_counter(), time.process_time()
    warm = cycle(fmt)
    warm_wall, warm_cpu = time.perf_counter()-wall, time.process_time()-cpu
    warm_cache = _eligible_rosters.cache_info()._asdict()
    assert cold == warm
    maps = {}
    for job in cold:
        name = job['meta']['map']
        if name in maps:
            continue
        identity = scenario_identity(job)
        identity.pop('factions')
        pools = _eligible_rosters(json.dumps(identity, sort_keys=True, separators=(',', ':')),
                                   tuple(params.FACTIONS))
        rosters = {roster for seat in pools for choices in seat for roster in choices}
        sizes = [len(choices) for seat in pools for choices in seat]
        maps[name] = dict(map_sha256=job['meta']['map_sha256'], eligible_ordered_rosters=len(rosters),
                          min_stratum_rosters=min(sizes), max_stratum_rosters=max(sizes))
    return dict(balance_cycle_games=len(cold), cold_wall_seconds=cold_wall,
                cold_cpu_seconds=cold_cpu, warm_wall_seconds=warm_wall, warm_cpu_seconds=warm_cpu,
                cold_cache=cold_cache, warm_cache=warm_cache, maps=maps,
                map_counts=dict(Counter(j['meta']['map'] for j in cold)),
                learner_faction_counts=dict(Counter(j['factions'][j['meta']['seat']-1] for j in cold)),
                distinct_scenarios_in_cycle=len({j['scenario_family'] for j in cold}),
                distinct_game_families_in_cycle=len({j['game_family'] for j in cold}),
                available_eligible_scenarios=sum(v['eligible_ordered_rosters'] for v in maps.values()),
                nominal_ordered_rosters_per_map=perm(len(params.FACTIONS), PLAYERS[fmt]),
                all_support_within_balance_cycles=max(v['max_stratum_rosters'] for v in maps.values()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    result = dict(source_commit=args.source, rules_sha256=schema()['rules_sha256'],
                  scope='schedule construction; no matches or learning', seed=19, max_turns=60,
                  note='Cold refers to the eligibility cache, not the filesystem; one measured cycle per case.',
                  formats={fmt: measure(fmt) for fmt in FORMATS})
    with args.output.open('x', encoding='utf-8') as output:
        output.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
