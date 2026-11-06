"""Balanced PPO strata over the frozen, eligible public scenario space."""
from functools import lru_cache
from itertools import permutations
import json

from .formats import PLAYERS
from .maps import SPLITS, _digest, bind_scenario, decorate, run_family, scenario_identity
from .data import split
import params


DESIGN = 'map-seat-faction-v1'


@lru_cache(maxsize=32)
def _eligible_rosters(identity_json, factions):
    """Cache only physical identity and the frozen faction inventory, never RNG/bots."""
    identity = json.loads(identity_json)
    players = PLAYERS[identity['format']]
    pools = [[[] for _ in factions] for _ in range(players)]
    faction_indexes = {name: index for index, name in enumerate(factions)}
    for roster in permutations(factions, players):
        identity['factions'] = roster
        if split(_digest(identity)) == 'train':
            for seat, faction in enumerate(roster):
                pools[seat][faction_indexes[faction]].append(roster)
    if any(not choices for seat in pools for choices in seat):
        raise ValueError('no eligible PPO roster for a required map/seat/faction stratum: '
                         + identity['format'])
    return tuple(tuple(tuple(choices) for choices in seat) for seat in pools)


def compose(job, *, max_turns):
    """Keep map weights and learner strata exact, then cycle each eligible roster pool."""
    fmt = job['meta']['format']
    players = PLAYERS[fmt]
    seat = job['meta']['seat']
    factions = tuple(params.FACTIONS)
    native_maps = len(SPLITS[fmt]['train'])
    map_slots = 2 * native_maps
    # Every group of N actual rollout jobs visits each learner seat exactly once.
    ordinal = job['training_scenario']['index'] // players
    focal = (ordinal + seat - 1) % len(factions)
    map_index = (ordinal // len(factions) + focal) % map_slots
    cycle = ordinal // (len(factions) * map_slots)
    decorate(job, fmt, map_index, 'train', max_turns=max_turns)

    identity = scenario_identity(job)
    identity.pop('factions')
    choices = _eligible_rosters(json.dumps(identity, sort_keys=True, separators=(',', ':')),
                                factions)[seat-1][focal]
    # Repeated arena slots advance one shared pool without changing its 50% share.
    visit = cycle * native_maps + map_index//2 if map_index % 2 == 0 else cycle
    roster_index = visit % len(choices)
    job['factions'] = list(choices[roster_index])
    job['game_family'] = run_family(job)
    bind_scenario(job)
    job['meta']['eligibility_swap'] = dict(design=DESIGN,
        requested_index=job['training_scenario']['index'], selected_map_index=map_index,
        learner_seat=seat, learner_faction=factions[focal], roster_index=roster_index,
        eligible_rosters=len(choices), balance_cycle_games=players*len(factions)*map_slots)
    return job
