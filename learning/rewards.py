"""Versioned training rewards. Judge labels must never enter actor inputs."""
from dataclasses import asdict, dataclass
import heapq
import math

FORMULA_ID = 'v5-potential-1'
RANGES = {'economy': (.05, .20), 'control': (.02, .15), 'explore': (0., .15)}


@dataclass(frozen=True)
class RewardConfig:
    economy: float = .15
    control: float = .10
    explore: float = .10
    mode: str = 'adaptive'
    entropy: float = .01
    bc_aux: float = .10
    gamma: float = 1.
    gae_lambda: float = .95
    reward_version: int = 0
    reward_formula_id: str = FORMULA_ID

    def __post_init__(self):
        if self.mode not in ('fixed', 'scheduled', 'adaptive'):
            raise ValueError('unknown reward mode')
        for name, (lo, hi) in RANGES.items():
            value = getattr(self, name)
            if not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f'{name} must be in [{lo}, {hi}]')
        for name in ('entropy', 'bc_aux'):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f'invalid {name}')
        if not 0 < self.gamma <= 1 or not 0 <= self.gae_lambda <= 1:
            raise ValueError('invalid discount')
        if type(self.reward_version) is not int or self.reward_version < 0:
            raise ValueError('invalid reward version')
        if self.reward_formula_id != FORMULA_ID:
            raise ValueError('unsupported reward formula')

    def to_dict(self):
        return asdict(self)


def terminal_rewards(result):
    """Return side-indexed rewards; FFA raw scores are centered together."""
    sides = list(range(1, len(result['bots']) + 1))
    teams = result.get('teams')
    if teams and len(set(teams)) < len(sides):
        winning = result.get('winning_team', 0)
        return {s: (0. if not winning else 1. if teams[s - 1] == winning else -1.) for s in sides}
    if len(sides) == 2:
        winner = result.get('winner', 0)
        return {s: (0. if not winner else 1. if s == winner else -1.) for s in sides}
    ranks = result.get('rank_points', result.get('ranks', {}))
    if not ranks:
        raise ValueError('FFA outcome lacks raw rank points')
    scores = {s: float(ranks.get(s, ranks.get(str(s), 0))) for s in sides}
    if not all(math.isfinite(v) for v in scores.values()):
        raise ValueError('nonfinite FFA outcome')
    mean = sum(scores.values()) / len(scores)
    scale = max(abs(v - mean) for v in scores.values())
    return {s: (v - mean) / scale if scale else 0. for s, v in scores.items()}


def economy_potential(side, sides, teams=None):
    """sides maps side IDs to {gold, units: [{cost,hp,max_hp}], villages}."""
    groups = {}
    for sid, state in sides.items():
        group = teams[sid] if teams else sid
        army = sum(float(u['cost']) * max(0., float(u['hp'])) / max(1., float(u['max_hp'])) for u in state['units'])
        groups.setdefault(group, []).append(float(state['gold']) + army + 20 * state['villages'])
    amounts = {g: sum(values) / len(values) for g, values in groups.items()}
    own = teams[side] if teams else side
    others = [v for group, v in amounts.items() if group != own]
    return (amounts[own] - sum(others) / len(others)) / (200 + sum(abs(v) for v in amounts.values())) if others else 0.


def transition_reward(now, following, config, *, terminal_reward=0., delta_turn=0, terminal=False, gamma=None, components=False):
    """`explored` is cumulative normalized area, not a per-decision bonus.

    A normal terminal zeros next potentials. A truncated trajectory must supply
    its legal end snapshot here and retain the matching value bootstrap.
    """
    config = config if isinstance(config, RewardConfig) else RewardConfig(**config)
    if delta_turn < 0:
        raise ValueError('negative own-turn span')
    gamma = config.gamma if gamma is None else gamma
    if not 0 < gamma <= 1:
        raise ValueError('invalid discount')
    discount = gamma ** delta_turn
    pieces = {'terminal': float(terminal_reward)}
    if not math.isfinite(pieces['terminal']):
        raise ValueError('nonfinite terminal reward')
    for name in ('economy', 'control'):
        a, b = float(now[name]), 0. if terminal else float(following[name])
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('nonfinite reward potential')
        pieces[name] = getattr(config, name) * (discount * b - a)
    before, after = float(now['explored']), float(following['explored'])
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (before, after)):
        raise ValueError('invalid cumulative exploration')
    explored = after - before
    if not math.isfinite(explored) or explored < -1e-9:
        raise ValueError('exploration counter regressed')
    pieces['explore'] = config.explore * min(1., max(0., explored))
    total = sum(pieces.values())
    return (total, pieces) if components else total


class ExplorationLedger:
    """The caller assigns scopes strictly from the scenario sharing contract."""
    def __init__(self, state=None):
        self.scopes = {key: {'seen': set(value['seen']), 'earned': value['earned']}
                       for key, value in (state or {}).items()}

    def observe(self, scope, visible_weights, total_weight, *, fog=True, initial=False):
        if total_weight <= 0:
            raise ValueError('explorable area must be positive')
        scope = str(scope)
        fresh = scope not in self.scopes
        state = self.scopes.setdefault(scope, {'seen': set(), 'earned': 0.})
        unseen = {key: value for key, value in visible_weights.items() if str(key) not in state['seen']}
        if any(not math.isfinite(v) or v < 0 for v in unseen.values()):
            raise ValueError('invalid exploration weight')
        state['seen'].update(str(key) for key in visible_weights)
        if fog and not initial and not fresh:
            state['earned'] = min(1., state['earned'] + sum(unseen.values()) / total_weight)
        return state['earned'] if fog else 0.

    def state_dict(self):
        return {key: {'seen': sorted(value['seen']), 'earned': value['earned']} for key, value in self.scopes.items()}


def hex_neighbors(cell):
    x, y = cell
    offset = x % 2
    return ((x, y - 1), (x, y + 1), (x - 1, y - offset),
            (x - 1, y + 1 - offset), (x + 1, y - offset), (x + 1, y + 1 - offset))


class ControlMap:
    """Bounded multi-source influence on *known* terrain, at most four graphs.

    movement_costs: {class: {known_cell: positive_cost}}; sources are legal own
    or visible/last-seen units, with cell/class/strength/age. Hidden game-state
    versions must not be used as view_version. Fixed total_weight is judge-only.
    """
    def __init__(self, radius=24., age_decay=.25):
        self.radius, self.age_decay = radius, age_decay
        self.cache = {}
        self.turn = None

    def _influence(self, costs, sources):
        distances, queue = {}, []
        for source in sources:
            cell = tuple(source['cell'])
            strength = min(1., max(0., source.get('strength', 1.))) * math.exp(-self.age_decay * source.get('age', 0))
            if cell in costs and strength > 0:
                distance = -math.log(strength) * self.radius
                if distance < distances.get(cell, math.inf):
                    distances[cell] = distance
                    heapq.heappush(queue, (distance, cell))
        while queue:
            distance, cell = heapq.heappop(queue)
            if distance != distances[cell] or distance > self.radius:
                continue
            for neighbor in hex_neighbors(cell):
                cost = costs.get(neighbor)
                if cost is None or not math.isfinite(cost) or cost <= 0:
                    continue
                candidate = distance + cost
                if candidate <= self.radius and candidate < distances.get(neighbor, math.inf):
                    distances[neighbor] = candidate
                    heapq.heappush(queue, (candidate, neighbor))
        return {cell: math.exp(-distance / self.radius) for cell, distance in distances.items() if distance <= self.radius}

    def potential(self, movement_costs, own, enemies, strategic_weights, total_weight, *, turn, view_version):
        if len(movement_costs) > 4:
            raise ValueError('control requires at most four movement graphs')
        if total_weight <= 0 or sum(strategic_weights.values()) > total_weight + 1e-6:
            raise ValueError('invalid fixed strategic normalization')
        if self.turn != turn:
            self.cache.clear()
            self.turn = turn
        influences = []
        for sources in (own, enemies):
            merged = {}
            for cls, costs in movement_costs.items():
                selected = [s for s in sources if s['class'] == cls]
                signature = tuple(sorted((tuple(s['cell']), s.get('strength', 1.), s.get('age', 0)) for s in selected))
                key = (view_version, cls, signature)
                if key not in self.cache:
                    # Each class keeps only this turn's own/enemy calculation.
                    self.cache[key] = self._influence(costs, selected)
                for cell, value in self.cache[key].items():
                    merged[cell] = max(merged.get(cell, 0.), value)
            influences.append(merged)
        a, b = influences
        score = .5 * total_weight
        for cell, weight in strategic_weights.items():
            x, y = a.get(cell, 0.), b.get(cell, 0.)
            fraction = x / (x + y) if x + y > 1e-12 else .5
            score += weight * (fraction - .5)
        # Do not retain previous observations within this turn indefinitely.
        self.cache = {key: value for key, value in self.cache.items() if key[0] == view_version}
        return max(0., min(1., score / total_weight))
