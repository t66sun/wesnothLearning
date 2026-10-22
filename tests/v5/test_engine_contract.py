"""Contract tests for the Rust lite engine (``_engine_lite``).

These tests exercise TEST.md sections 4.1-4.3 and 5 against the production
Lua host modules loaded by ``tests/v5/helpers.engine``.  They are LiteEngine
evidence only: no native Wesnoth binary, map or ruleset is involved here.
"""

import copy
import json
import unittest

from _engine_lite import ENGINE_VERSION, LiteEngine, RNG_VERSION

from tests.v5 import helpers as H

WIDTH = 8
HEIGHT = 6
PLAIN = ["Gg"] * (WIDTH * HEIGHT)


def _dumps(value):
    return json.dumps(value)


def _strip_timing(decision):
    result = copy.deepcopy(decision)
    result.get("timing", {}).pop("ms", None)
    return result


def _policy_view(decision):
    """Decision as an actor may see it: no judge-only reward and no wall clock."""
    result = _strip_timing(decision)
    result.pop("reward_raw", None)
    return result


def _observe_batch(engine, sides):
    return json.loads(engine.observe_batch(_dumps(sides)))


def _legal_batch(engine, sides):
    return json.loads(engine.legal_batch(_dumps(sides)))


def _step_batch(engine, actions):
    return json.loads(engine.step_batch(_dumps(actions)))


def _unit_row(unit_type, side, x, y, *, uid=None, rules_data=None, leader=False,
              hp=None, moves=None, xp=0, status=()):
    base = (rules_data or H.rules())["units"][unit_type]
    return {
        "id": uid or "u{}-{}-{}".format(side, x, y),
        "unit_type": unit_type,
        "side": side,
        "pos": y * WIDTH + x,
        "hp": base["hp"] if hp is None else hp,
        "moves": base["moves"] if moves is None else moves,
        "attacks_left": 1,
        "leader": leader,
        "xp": xp,
        "status": list(status),
        "traits": [],
        "acted": False,
    }


def _bare_unit(uid, unit_type, side, x, y, *, leader=False):
    return {
        "id": uid,
        "unit_type": unit_type,
        "side": side,
        "pos": y * WIDTH + x,
        "hp": 10,
        "moves": 1,
        "attacks_left": 1,
        "leader": leader,
        "xp": 0,
        "status": [],
        "traits": [],
        "acted": False,
    }


def _spec(units, terrain=None, *, fog=True, shroud=False):
    codes = list(terrain) if terrain is not None else list(PLAIN)
    return H.spec(width=WIDTH, height=HEIGHT, units=units, terrain=codes,
                  fog=fog, shroud=shroud)


def _engine(units, terrain=None, *, rules_data=None, fog=True, shroud=False):
    return H.engine(game_spec=_spec(units, terrain, fog=fog, shroud=shroud),
                    rules_data=rules_data)


def _unit_at(engine, side, unit_id):
    for unit in H.observe(engine, side)["units"]:
        if unit["id"] == unit_id:
            return unit
    return None


def _side_at(engine, side_id, viewer=1):
    for row in H.observe(engine, viewer)["sides"]:
        if row["id"] == side_id:
            return row
    return None


def _destinations(engine, unit_id, side=1):
    return {(action["to"] % WIDTH + 1, action["to"] // WIDTH + 1)
            for action in H.legal(engine, side)
            if action.get("kind") == "move" and action.get("unit") == unit_id}


def _odd_q_neighbors(cell):
    """TEST.md 4.2: 1-based odd-q relation ``{(x,y±1),(x±1,y),(x±1,y+dy)}``."""
    x, y = cell
    dy = -1 if x % 2 else 1
    candidates = (
        (x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y),
        (x - 1, y + dy), (x + 1, y + dy),
    )
    return {(cx, cy) for cx, cy in candidates
            if 1 <= cx <= WIDTH and 1 <= cy <= HEIGHT}


def _hex_ring(center, radius):
    ring = {center}
    frontier = {center}
    for _ in range(radius):
        frontier = {neighbor for cell in frontier
                    for neighbor in _odd_q_neighbors(cell)}
        ring |= frontier
    return ring


class EngineIdentityTest(unittest.TestCase):

    def test_module_and_snapshot_identity(self):
        self.assertEqual(ENGINE_VERSION, "lite-0.1")
        self.assertEqual(RNG_VERSION, "xoshiro256++-1")
        self.assertIsInstance(LiteEngine, type)
        engine = H.engine()
        snapshot = H.snapshot(engine)
        self.assertEqual(snapshot["engine_id"], "lite-0.1")
        self.assertEqual(snapshot["rng_version"], "xoshiro256++-1")
        observation = H.observe(engine, 1)
        self.assertEqual(observation["engine_id"], "lite-0.1")
        self.assertEqual(observation["rng_version"], "xoshiro256++-1")
        self.assertEqual(observation["rules_version"], "synthetic-v5")
        self.assertTrue(observation["approximate"])

    def test_reset_is_deterministic(self):
        engine = H.engine()
        game_spec = H.spec()
        observation = H.observe(engine, 1)
        legal = H.legal(engine, 1)
        engine.reset(_dumps(game_spec))
        self.assertEqual(H.observe(engine, 1), observation)
        self.assertEqual(H.legal(engine, 1), legal)
        twin = H.engine(game_spec=game_spec)
        self.assertEqual(H.observe(twin, 1), observation)
        self.assertEqual(H.legal(twin, 1), legal)

    def test_reset_keeps_the_lua_host_usable(self):
        """Reset rebuilds both the Rust state and the configured Lua host."""
        engine = H.engine()
        engine.reset(_dumps(H.spec()))
        H.decision(engine, 1)


class BatchApiTest(unittest.TestCase):

    def test_batch_results_match_sequential_calls(self):
        engine = H.engine()
        start = H.snapshot(engine)
        self.assertEqual(_observe_batch(engine, [1, 2]),
                         [H.observe(engine, 1), H.observe(engine, 2)])
        self.assertEqual(_legal_batch(engine, [1, 2]),
                         [H.legal(engine, 1), H.legal(engine, 2)])
        actions = [
            {"kind": "attack", "unit": "p1", "target": "e1", "weapon": 0},
            {"kind": "end_turn"},
            {"kind": "end_turn"},
        ]
        sequential = [H.step(engine, action) for action in actions]
        sequential_snapshot = H.snapshot(engine)
        sequential_views = [_observe_batch(engine, [1, 2]),
                            _legal_batch(engine, [1, 2])]
        H.restore(engine, start)
        batched = _step_batch(engine, actions)
        self.assertEqual(len(batched), len(actions))
        self.assertEqual(batched, sequential)
        self.assertEqual(H.snapshot(engine), sequential_snapshot)
        self.assertEqual([_observe_batch(engine, [1, 2]),
                          _legal_batch(engine, [1, 2])], sequential_views)

    def test_illegal_batch_is_atomic(self):
        engine = H.engine()
        start = H.snapshot(engine)
        observations = _observe_batch(engine, [1, 2])
        legal = _legal_batch(engine, [1, 2])
        with self.assertRaisesRegex(ValueError, "legal intents"):
            _step_batch(engine, [
                {"kind": "end_turn"},
                {"kind": "move", "unit": "p1", "to": 0},
            ])
        self.assertEqual(H.snapshot(engine), start)
        self.assertEqual(H.snapshot(engine)["game"]["revision"],
                         start["game"]["revision"])
        self.assertEqual(_observe_batch(engine, [1, 2]), observations)
        self.assertEqual(_legal_batch(engine, [1, 2]), legal)


class IllegalActionTest(unittest.TestCase):

    def test_illegal_actions_are_rejected_without_side_effects(self):
        engine = H.engine()
        start = H.snapshot(engine)
        cases = [
            {"kind": "move", "unit": "p1", "to": 19},       # own tile
            {"kind": "move", "unit": "p1", "to": 20},       # enemy occupied
            {"kind": "attack", "unit": "p1", "target": "e2", "weapon": 0},
            {"kind": "attack", "unit": "p1", "target": "e1", "weapon": 9},
            {"kind": "recruit", "unit_type": "Fighter", "to": 33},
            {"kind": "move", "unit": "e1", "to": 19},       # non-current side
            {"kind": "teleport"},                           # unknown variant
        ]
        for action in cases:
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    H.step(engine, action)
                self.assertEqual(H.snapshot(engine), start)

    def test_non_current_side_has_no_legal_actions(self):
        engine = H.engine()
        self.assertEqual(H.legal(engine, 2), [])
        self.assertEqual(H.observe(engine, 2)["side"], 2)
        self.assertIsNotNone(_side_at(engine, 2, viewer=2)["gold"])
        for row in H.observe(engine, 2)["sides"]:
            if row["id"] != 2:
                self.assertIsNone(row.get("gold"))
                self.assertIsNone(row.get("recruit"))
        for side in (0, 3):
            with self.subTest(side=side):
                with self.assertRaisesRegex(ValueError, "invalid side"):
                    H.observe(engine, side)
                with self.assertRaisesRegex(ValueError, "invalid side"):
                    H.legal(engine, side)

    def test_actions_for_the_previous_side_are_rejected_after_end_turn(self):
        engine = H.engine()
        H.step(engine, {"kind": "end_turn"})
        self.assertEqual(H.observe(engine, 1)["current_side"], 2)
        self.assertEqual(H.legal(engine, 1), [])
        self.assertNotEqual(H.legal(engine, 2), [])
        for row in H.observe(engine, 1)["sides"]:
            if row["id"] != 1:
                self.assertIsNone(row.get("gold"))
        with self.assertRaisesRegex(ValueError, "legal intents"):
            H.step(engine, {"kind": "move", "unit": "p1", "to": 18})


class HexGeometryTest(unittest.TestCase):

    @staticmethod
    def _scout_engine(cx, cy, moves):
        rules = H.rules()
        rules["units"]["Scout"] = H._unit_type("Scout", moves=moves, hp=10, cost=10)
        center = (cx + 1, cy + 1)
        blocked = _hex_ring(center, moves)
        enemy = next(
            cell for cell in ((7, 5), (0, 0), (7, 0), (0, 5), (4, 3))
            if cell != (cx, cy) and (cell[0] + 1, cell[1] + 1) not in blocked)
        units = [
            _unit_row("Scout", 1, cx, cy, uid="s1", rules_data=rules, leader=True),
            _unit_row("Fighter", 2, enemy[0], enemy[1], uid="e1",
                      rules_data=rules, leader=True),
        ]
        return H.engine(game_spec=_spec(units), rules_data=rules)

    def test_adjacent_destinations_match_the_odd_q_formula(self):
        for cx, cy in ((3, 3), (4, 3), (2, 2), (0, 2), (7, 5), (7, 0), (0, 0)):
            center = (cx + 1, cy + 1)
            engine = self._scout_engine(cx, cy, 1)
            destinations = _destinations(engine, "s1")
            with self.subTest(center=center):
                self.assertEqual(destinations, _odd_q_neighbors(center))
                for destination in destinations:
                    self.assertIn(center, _odd_q_neighbors(destination))

    def test_odd_q_relation_is_symmetric(self):
        for x in range(1, WIDTH + 1):
            for y in range(1, HEIGHT + 1):
                for neighbor in _odd_q_neighbors((x, y)):
                    self.assertIn((x, y), _odd_q_neighbors(neighbor))

    def test_two_ring_expansion_contains_nineteen_cells(self):
        center = (4, 3)
        ring = _hex_ring(center, 2)
        self.assertEqual(len(ring), 19)
        engine = self._scout_engine(3, 2, 2)
        destinations = _destinations(engine, "s1")
        self.assertEqual(destinations, ring - {center})
        self.assertEqual(len(destinations), 18)

    def test_zero_based_row_major_mapping_round_trips(self):
        engine = self._scout_engine(3, 3, 1)
        moves = [action for action in H.legal(engine, 1)
                 if action.get("kind") == "move"]
        self.assertTrue(moves)
        for action in moves:
            pos = action["to"]
            x, y = pos % WIDTH, pos // WIDTH
            self.assertEqual(y * WIDTH + x, pos)
            self.assertEqual((x + 1, y + 1),
                             (pos % WIDTH + 1, pos // WIDTH + 1))
            self.assertLess(pos, WIDTH * HEIGHT)


class MovementTest(unittest.TestCase):

    def test_move_costs_and_remaining_movement(self):
        terrain = list(PLAIN)
        terrain[9] = "Mm"
        units = [_unit_row("Fighter", 1, 1, 2, uid="p1", leader=True),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        engine = _engine(units, terrain)
        result = H.step(engine, {"kind": "move", "unit": "p1", "to": 9})
        self.assertEqual(result["actual_pos"], 9)
        self.assertFalse(result["interrupted"])
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 3)

        engine = _engine(units, PLAIN)
        H.step(engine, {"kind": "move", "unit": "p1", "to": 16})
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 4)

    def test_full_move_consumes_all_remaining_movement(self):
        units = [_unit_row("Fighter", 1, 1, 2, uid="p1", leader=True),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        engine = _engine(units, PLAIN)
        result = H.step(engine, {"kind": "move", "unit": "p1", "to": 1,
                                 "full": False})
        self.assertEqual(result["actual_pos"], 1)
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 3)

        engine = _engine(units, PLAIN)
        result = H.step(engine, {"kind": "move", "unit": "p1", "to": 1,
                                 "full": True})
        self.assertEqual(result["actual_pos"], 1)
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 0)

    def test_occupied_tiles_block_movement_and_stacking(self):
        engine = H.engine()
        destinations = {(action["to"] % WIDTH + 1,
                         action["to"] // WIDTH + 1)
                        for action in H.legal(engine, 1)
                        if action.get("kind") == "move"
                        and action.get("unit") == "p1"}
        self.assertNotIn((5, 3), destinations)   # e1 at 0-based (4,2)
        self.assertNotIn((3, 4), destinations)   # p2 at 0-based (2,3)

        units = [_unit_row("Fighter", 1, 0, 2, uid="p1", leader=True),
                 _unit_row("Fighter", 1, 1, 2, uid="p2"),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        engine = _engine(units, PLAIN)
        destinations = {action["to"] for action in H.legal(engine, 1)
                        if action.get("kind") == "move"
                        and action.get("unit") == "p1"}
        self.assertNotIn(17, destinations)
        self.assertIn(18, destinations)
        with self.assertRaisesRegex(ValueError, "legal intents"):
            H.step(engine, {"kind": "move", "unit": "p1", "to": 17})

    def test_friendly_units_can_be_passed_through(self):
        """Reach and execution agree that living allies are traversable."""
        units = [_unit_row("Fighter", 1, 0, 2, uid="p1", leader=True),
                 _unit_row("Fighter", 1, 1, 2, uid="p2"),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        engine = _engine(units, PLAIN)
        destinations = {action["to"] for action in H.legal(engine, 1)
                        if action.get("kind") == "move"
                        and action.get("unit") == "p1"}
        self.assertIn(18, destinations)
        result = H.step(engine, {"kind": "move", "unit": "p1", "to": 18})
        self.assertEqual(result["actual_pos"], 18)
        self.assertFalse(result["interrupted"])

    def test_village_capture_zeroes_moves_and_changes_owner(self):
        engine = H.engine()
        self.assertEqual(H.observe(engine, 1)["villages"]["18"][0], 0)
        result = H.step(engine, {"kind": "move", "unit": "p1", "to": 18})
        self.assertEqual(result["actual_pos"], 18)
        self.assertFalse(result["interrupted"])
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 0)
        self.assertEqual(H.observe(engine, 1)["villages"]["18"][0], 1)

    def test_total_income_is_gross_and_counts_owned_villages(self):
        terrain = list(PLAIN)
        terrain[18] = "Gg^Vh"
        units = [
            _unit_row("Fighter", 1, 0, 0, uid="p1", leader=True),
            _unit_row("Fighter", 1, 1, 0, uid="p2"),
            _unit_row("Fighter", 1, 2, 0, uid="p3"),
            _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True),
        ]
        game_spec = _spec(units, terrain)
        game_spec["village_owner"] = {18: 1}
        engine = H.engine(game_spec=game_spec)
        # base 2 + one owned village at 2 gold. Two non-leader levels cost two
        # upkeep, but native side.total_income is gross; expenses are separate.
        self.assertEqual(_side_at(engine, 1)["total_income"], 4)

    def test_recruit_from_connected_castle_pays_gold(self):
        engine = H.engine()
        slots = sorted({action["to"] for action in H.legal(engine, 1)
                        if action["kind"] == "recruit"})
        self.assertEqual(slots, [11])
        gold_before = _side_at(engine, 1)["gold"]
        result = H.step(engine, {"kind": "recruit", "unit_type": "Fighter",
                                 "to": 11})
        self.assertEqual(result["actual_pos"], 11)
        self.assertFalse(result["interrupted"])
        self.assertEqual(_side_at(engine, 1)["gold"], gold_before - 14)
        recruited = [unit for unit in H.observe(engine, 1)["units"]
                     if unit["pos"] == 11]
        self.assertEqual(len(recruited), 1)
        self.assertEqual((recruited[0]["moves"], recruited[0]["attacks_left"]),
                         (0, 0))
        self.assertEqual([action for action in H.legal(engine, 1)
                          if action["kind"] == "recruit"], [])

    def test_recruit_requires_a_castle_connected_to_the_keep(self):
        terrain = list(PLAIN)
        terrain[9] = "Gg^Kh"
        terrain[10] = "Gg^Ch"
        terrain[47] = "Gg^Ch"
        units = [_unit_row("Fighter", 1, 1, 1, uid="p1", leader=True),
                 _unit_row("Fighter", 2, 0, 5, uid="e1", leader=True)]
        engine = _engine(units, terrain)
        slots = sorted({action["to"] for action in H.legal(engine, 1)
                        if action["kind"] == "recruit"})
        self.assertEqual(slots, [10])
        with self.assertRaisesRegex(ValueError, "legal intents"):
            H.step(engine, {"kind": "recruit", "unit_type": "Fighter", "to": 47})

    def test_recruit_stops_when_the_leader_leaves_the_keep(self):
        engine = H.engine()
        H.step(engine, {"kind": "move", "unit": "p1", "to": 18})
        self.assertEqual([action for action in H.legal(engine, 1)
                          if action["kind"] == "recruit"], [])

    def test_multiple_leaders_are_allowed(self):
        terrain = list(PLAIN)
        terrain[9] = "Gg^Kh"
        terrain[10] = "Gg^Ch"
        terrain[37] = "Gg^Kh"
        terrain[38] = "Gg^Ch"
        units = [
            _unit_row("Fighter", 1, 1, 1, uid="p1", leader=True),
            _unit_row("Fighter", 1, 5, 4, uid="p1b", leader=True),
            _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True),
        ]
        engine = _engine(units, terrain)
        slots = sorted({action["to"] for action in H.legal(engine, 1)
                        if action["kind"] == "recruit"})
        self.assertEqual(slots, [10, 38])

    def test_slow_doubles_movement_cost(self):
        terrain = list(PLAIN)
        terrain[9] = "Mm"
        units = [_unit_row("Fighter", 1, 1, 2, uid="p1", leader=True,
                           status=("slowed",)),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        engine = _engine(units, terrain)
        H.step(engine, {"kind": "move", "unit": "p1", "to": 9})
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 1)

        control = [_unit_row("Fighter", 1, 1, 2, uid="p1", leader=True),
                   _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        engine = _engine(control, terrain)
        H.step(engine, {"kind": "move", "unit": "p1", "to": 9})
        self.assertEqual(_unit_at(engine, 1, "p1")["moves"], 3)

    def test_teleport_requires_the_rules_ability(self):
        def build(with_ability):
            rules = H.rules()
            rules["units"]["Scout"] = H._unit_type("Scout", moves=1, hp=10, cost=10)
            rules["units"]["Ghostwalk"] = H._unit_type(
                "Ghostwalk", moves=1, hp=10, cost=10, abilities=["teleport"])
            terrain = list(PLAIN)
            terrain[18] = "Gg^Vh"
            terrain[47] = "Gg^Vh"
            units = [
                _unit_row("Scout", 1, 6, 4, uid="p1", rules_data=rules,
                          leader=True),
                _unit_row("Ghostwalk" if with_ability else "Scout", 1, 2, 2,
                          uid="p2", rules_data=rules),
                _unit_row("Fighter", 2, 0, 0, uid="e1", rules_data=rules,
                          leader=True),
            ]
            game_spec = _spec(units, terrain)
            game_spec["village_owner"] = {18: 1, 47: 1}
            return H.engine(game_spec=game_spec, rules_data=rules)

        engine = build(True)
        destinations = {action["to"] for action in H.legal(engine, 1)
                        if action.get("unit") == "p2"}
        self.assertIn(47, destinations)
        result = H.step(engine, {"kind": "move", "unit": "p2", "to": 47})
        self.assertEqual(result["actual_pos"], 47)
        self.assertEqual(_unit_at(engine, 1, "p2")["moves"], 0)

        engine = build(False)
        self.assertNotIn(47, {action["to"] for action in H.legal(engine, 1)
                              if action.get("unit") == "p2"})

    def test_unsupported_declarations_are_rejected(self):
        rules = H.rules()
        rules["units"]["Scout"] = H._unit_type(
            "Scout", moves=1, hp=10, cost=10,
            unsupported=["weapon special:foo"])
        units = [_unit_row("Scout", 1, 2, 2, uid="p1", rules_data=rules,
                           leader=True),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", rules_data=rules,
                           leader=True)]
        with self.assertRaisesRegex(ValueError, "unimplemented declarations"):
            H.engine(game_spec=_spec(units), rules_data=rules)


def _combat_engine(attacker_type, defender_type, *, rules_data=None,
                   defender_hp=None, attacker_xp=0, inject=None, terrain=None):
    rules = rules_data or H.rules()
    codes = list(terrain) if terrain is not None else list(PLAIN)
    units = [
        _unit_row(attacker_type, 1, 2, 2, uid="a1", rules_data=rules,
                  leader=True, xp=attacker_xp),
        _unit_row(defender_type, 2, 3, 2, uid="d1", rules_data=rules,
                  leader=True, hp=defender_hp),
    ]
    engine = H.engine(game_spec=_spec(units, codes), rules_data=rules)
    if inject is not None:
        engine.inject_hits(_dumps(inject))
    return engine


def _attack(engine, weapon=0):
    return H.step(engine, {"kind": "attack", "unit": "a1", "target": "d1",
                           "weapon": weapon})


class CombatTest(unittest.TestCase):

    def test_strike_chance_equals_terrain_defense(self):
        terrain = list(PLAIN)
        terrain[19] = "Ss"
        engine = _combat_engine("Archer", "Skeleton", terrain=terrain,
                                inject=[True, True, True])
        result = _attack(engine)
        attacker_strikes = [strike for strike in result["strikes"]
                            if strike["attacker"] == "a1"]
        self.assertTrue(attacker_strikes)
        self.assertEqual({strike["chance"] for strike in attacker_strikes}, {60})

    def test_magical_attack_uses_seventy_percent(self):
        terrain = list(PLAIN)
        terrain[19] = "Ss"
        engine = _combat_engine("Mage", "Fighter", terrain=terrain,
                                inject=[True, True, True])
        strikes = [strike for strike in _attack(engine)["strikes"]
                   if strike["attacker"] == "a1"]
        self.assertTrue(strikes)
        self.assertEqual({strike["chance"] for strike in strikes}, {70})

    def test_marksman_has_a_sixty_percent_floor(self):
        rules = H.rules()
        rules["units"]["Sniper"] = H._unit_type("Sniper", weapons=[
            {"id": "shot", "damage": 4, "strikes": 2, "damage_type": "pierce",
             "range": "ranged", "specials": ["marksman"]}])
        engine = _combat_engine("Sniper", "Fighter", rules_data=rules,
                                inject=[True, True])
        strikes = [strike for strike in _attack(engine)["strikes"]
                   if strike["attacker"] == "a1"]
        self.assertTrue(strikes)
        self.assertEqual({strike["chance"] for strike in strikes}, {60})

    def test_damage_follows_the_wesnoth_resistance_convention(self):
        """The frozen ``resistance`` map stores percent damage taken (100 =
        no resistance), matching freeze.py's ``100 - resistance_against``.
        """
        engine = _combat_engine("Fighter", "Skeleton", inject=[True, True])
        plain = _attack(engine)["strikes"][0]["damage"]

        rules = H.rules()
        rules["units"]["Skeleton"]["resistance"]["blade"] = 125
        engine = _combat_engine("Fighter", "Skeleton", rules_data=rules,
                                inject=[True, True])
        vulnerable = _attack(engine)["strikes"][0]["damage"]
        self.assertEqual((plain, vulnerable), (5, 6))

    def test_injected_hits_follow_per_strike_order_and_stop_on_death(self):
        engine = _combat_engine("Fighter", "Fighter", defender_hp=7,
                                inject=[True, False, True])
        result = _attack(engine)
        self.assertEqual([(strike["attacker"], strike["hit"])
                          for strike in result["strikes"]],
                         [("a1", True), ("d1", False), ("a1", True)])
        self.assertEqual(result["strikes"][0]["defender_hp"], 2)
        self.assertEqual(result["strikes"][1]["defender_hp"], 40)
        self.assertEqual(result["strikes"][-1]["defender_hp"], 0)
        self.assertTrue(result["finished"])
        self.assertEqual(result["winner"], "A")
        self.assertTrue(_side_at(engine, 2)["eliminated"])
        self.assertEqual(_unit_at(engine, 1, "a1")["xp"], 8)

    def test_xp_is_awarded_per_surviving_strike(self):
        engine = _combat_engine("Fighter", "Fighter", inject=[False] * 6)
        result = _attack(engine)
        self.assertFalse(result["finished"])
        self.assertEqual(_unit_at(engine, 1, "a1")["xp"], 1)
        self.assertEqual(_unit_at(engine, 1, "d1")["xp"], 1)

    def test_advancement_happens_at_max_experience(self):
        rules = H.rules()
        rules["units"]["Fighter"] = H._unit_type(
            "Fighter", experience=5, advances_to=["Veteran"],
            weapons=[{"id": "sword", "damage": 5, "strikes": 3,
                      "damage_type": "blade", "range": "melee"}])
        rules["units"]["Veteran"] = H._unit_type("Veteran", hp=55, moves=5,
                                                 cost=20, level=2)
        engine = _combat_engine("Fighter", "Fighter", rules_data=rules,
                                defender_hp=2, inject=[True] * 6)
        _attack(engine)
        attacker = _unit_at(engine, 1, "a1")
        self.assertEqual(attacker["unit_type"], "Veteran")
        self.assertEqual(attacker["hp"], 55)
        self.assertEqual(attacker["xp"], 3)

    def test_poison_and_slow_apply_only_to_a_surviving_defender(self):
        rules = H.rules()
        rules["units"]["Poisoner"] = H._unit_type("Poisoner", weapons=[
            {"id": "fangs", "damage": 2, "strikes": 2,
             "damage_type": "blade", "range": "melee",
             "specials": ["poison", "slow"]}])

        engine = _combat_engine("Poisoner", "Fighter", rules_data=rules,
                                inject=[True] * 6)
        _attack(engine)
        self.assertEqual(sorted(_unit_at(engine, 1, "d1")["status"]),
                         ["poisoned", "slowed"])

        engine = _combat_engine("Poisoner", "Fighter", rules_data=rules,
                                inject=[False] * 6)
        _attack(engine)
        self.assertEqual(_unit_at(engine, 1, "d1")["status"], [])

        engine = _combat_engine("Poisoner", "Fighter", rules_data=rules,
                                defender_hp=1, inject=[True] * 6)
        result = _attack(engine)
        self.assertEqual(len(result["strikes"]), 1)
        self.assertEqual(result["strikes"][0]["defender_hp"], 0)
        self.assertIsNone(_unit_at(engine, 1, "d1"))

    def test_leader_death_eliminates_the_side_and_ends_the_game(self):
        engine = _combat_engine("Fighter", "Fighter", defender_hp=1,
                                inject=[True, True])
        result = _attack(engine)
        self.assertTrue(result["finished"])
        self.assertEqual(result["winner"], "A")
        self.assertTrue(_side_at(engine, 2)["eliminated"])
        with self.assertRaisesRegex(ValueError, "game has ended"):
            H.step(engine, {"kind": "end_turn"})

    def test_forecast_bounds_and_statistics(self):
        engine = H.engine()
        for samples in (1, 4096):
            with self.subTest(samples=samples):
                forecast = json.loads(engine.forecast(1, "p1", "e1", 0, samples))
                self.assertEqual(forecast["samples"], samples)
        for samples in (0, 4097):
            with self.subTest(samples=samples):
                with self.assertRaisesRegex(ValueError, r"\[1,4096\]"):
                    engine.forecast(1, "p1", "e1", 0, samples)
        with self.assertRaisesRegex(ValueError, "invalid weapon"):
            engine.forecast(1, "p1", "e1", 9, 16)

        first = json.loads(engine.forecast(1, "p1", "e1", 0, 512))
        second = json.loads(engine.forecast(1, "p1", "e1", 0, 512))
        self.assertEqual(first, second)
        for role, max_hp in (("attacker", 40), ("defender", 40)):
            stats = first[role]
            with self.subTest(role=role):
                self.assertAlmostEqual(sum(stats["hp_chance"].values()), 1.0,
                                       places=9)
                for hp in stats["hp_chance"]:
                    self.assertGreaterEqual(int(hp), 0)
                    self.assertLessEqual(int(hp), max_hp)
                self.assertGreaterEqual(stats["average_hp"], 0)
                self.assertLessEqual(stats["average_hp"], max_hp)
                self.assertGreaterEqual(stats["poisoned"], 0)
                self.assertLessEqual(stats["poisoned"], 1)
                self.assertGreaterEqual(stats["slowed"], 0)
                self.assertLessEqual(stats["slowed"], 1)


def _hidden_spec(*, enemy_pos=47, enemy_hp=40, enemy_status=(),
                 terrain=None, village_owner=None):
    codes = list(terrain) if terrain is not None else list(PLAIN)
    if codes[47] == "Gg":
        codes[47] = "Gg^Vh"
    units = [
        _unit_row("Fighter", 1, 0, 0, uid="p1", leader=True),
        _unit_row("Fighter", 2, enemy_pos % WIDTH, enemy_pos // WIDTH,
                  uid="e1", leader=True, hp=enemy_hp, status=enemy_status),
    ]
    game_spec = H.spec(width=WIDTH, height=HEIGHT, units=units, terrain=codes,
                       fog=True, shroud=True)
    if village_owner is not None:
        game_spec["village_owner"] = dict(village_owner)
    return game_spec


class InformationIsolationTest(unittest.TestCase):

    def _hidden_baseline(self):
        engine = H.engine(game_spec=_hidden_spec())
        return (H.observe(engine, 1), H.legal(engine, 1),
                _policy_view(H.decision(engine, 1)))

    def test_hidden_enemy_state_does_not_leak(self):
        observation, legal, decision = self._hidden_baseline()
        self.assertNotIn("e1", [unit["id"] for unit in observation["units"]])
        self.assertFalse(observation["visible"][47])
        self.assertIsNone(observation["terrain"][47])

        variants = {
            "position": _hidden_spec(enemy_pos=41),
            "hp": _hidden_spec(enemy_hp=7),
            "status": _hidden_spec(enemy_status=("poisoned", "slowed")),
        }
        for name, game_spec in variants.items():
            engine = H.engine(game_spec=game_spec)
            with self.subTest(variant=name):
                self.assertEqual(H.observe(engine, 1), observation)
                self.assertEqual(H.legal(engine, 1), legal)
                self.assertEqual(_policy_view(H.decision(engine, 1)), decision)

    def test_hidden_terrain_does_not_leak(self):
        observation, legal, decision = self._hidden_baseline()
        codes = list(PLAIN)
        codes[41] = "Gg^Ch"
        engine = H.engine(game_spec=_hidden_spec(terrain=codes))
        self.assertEqual(H.observe(engine, 1), observation)
        self.assertEqual(H.legal(engine, 1), legal)
        self.assertEqual(_policy_view(H.decision(engine, 1)), decision)

    def test_hidden_village_ownership_does_not_leak_into_observation(self):
        base = H.engine(game_spec=_hidden_spec())
        changed = H.engine(game_spec=_hidden_spec(village_owner={47: 1}))
        self.assertEqual(H.legal(changed, 1), H.legal(base, 1))
        self.assertEqual(H.observe(changed, 1), H.observe(base, 1))

    def test_hidden_village_ownership_does_not_leak_into_decision(self):
        base = H.engine(game_spec=_hidden_spec())
        changed = H.engine(game_spec=_hidden_spec(village_owner={47: 1}))
        self.assertEqual(H.legal(changed, 1), H.legal(base, 1))
        self.assertEqual(_policy_view(H.decision(changed, 1)),
                         _policy_view(H.decision(base, 1)))

    def test_visible_enemy_changes_do_change_views(self):
        units = [
            _unit_row("Fighter", 1, 3, 2, uid="p1", leader=True),
            _unit_row("Archer", 1, 2, 3, uid="p2"),
            _unit_row("Fighter", 2, 4, 2, uid="e1", leader=True),
            _unit_row("Skeleton", 2, 5, 4, uid="e2"),
        ]
        changed = copy.deepcopy(units)
        changed[2]["hp"] = 30
        base = H.engine(game_spec=_spec(units))
        alternative = H.engine(game_spec=_spec(changed))
        self.assertNotEqual(H.observe(base, 1), H.observe(alternative, 1))
        self.assertNotEqual(_policy_view(H.decision(base, 1)),
                            _policy_view(H.decision(alternative, 1)))


class SnapshotTest(unittest.TestCase):

    def test_snapshot_restore_round_trips_views_and_decisions(self):
        engine = H.engine()
        snapshot = H.snapshot(engine)
        observation = H.observe(engine, 1)
        legal = H.legal(engine, 1)
        decision = _policy_view(H.decision(engine, 1))

        H.step(engine, {"kind": "move", "unit": "p1", "to": 18})
        H.step(engine, {"kind": "end_turn"})
        H.step(engine, {"kind": "end_turn"})
        self.assertNotEqual(H.observe(engine, 1), observation)

        H.restore(engine, snapshot)
        self.assertEqual(H.observe(engine, 1), observation)
        self.assertEqual(H.legal(engine, 1), legal)
        self.assertEqual(H.snapshot(engine), snapshot)
        self.assertEqual(_policy_view(H.decision(engine, 1)), decision)

    def test_restore_rejects_engine_and_rules_mismatch(self):
        engine = H.engine()
        snapshot = H.snapshot(engine)

        wrong_engine = copy.deepcopy(snapshot)
        wrong_engine["engine_id"] = "native-1.0"
        with self.assertRaisesRegex(ValueError, "snapshot version mismatch"):
            H.restore(engine, wrong_engine)

        wrong_rng = copy.deepcopy(snapshot)
        wrong_rng["rng_version"] = "mt19937"
        with self.assertRaisesRegex(ValueError, "snapshot version mismatch"):
            H.restore(engine, wrong_rng)

        wrong_rules = copy.deepcopy(snapshot)
        wrong_rules["game"]["rules"]["source_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "snapshot rules hash mismatch"):
            H.restore(engine, wrong_rules)

        with self.assertRaises(ValueError):
            H.restore(engine, "{")
        self.assertEqual(H.snapshot(engine), snapshot)


class SpecValidationTest(unittest.TestCase):

    def test_invalid_specs_are_rejected(self):
        duplicate = [_unit_row("Fighter", 1, 2, 2, uid="p1", leader=True),
                     _unit_row("Fighter", 1, 2, 2, uid="p2"),
                     _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)]
        cases = [
            ("single_side", lambda: H.engine(game_spec=H.spec(sides=1)),
             "invalid map, sides or turn limit"),
            ("approximate_required",
             lambda: H.engine(game_spec=H.spec(allow_approximate=False)),
             "requires allow_approximate=true"),
            ("unknown_terrain",
             lambda: H.engine(game_spec=H.spec(terrain=["Xx"] * 48)),
             "unknown terrain Xx"),
            ("unknown_type",
             lambda: H.engine(game_spec=_spec([
                 _bare_unit("p1", "Dragon", 1, 2, 2, leader=True),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)])),
             "missing type Dragon"),
            ("duplicate_position",
             lambda: H.engine(game_spec=_spec(duplicate)),
             "invalid unit p2"),
            ("side_without_leader",
             lambda: H.engine(game_spec=_spec([
                 _unit_row("Fighter", 1, 2, 2, uid="p1"),
                 _unit_row("Fighter", 2, 7, 5, uid="e1", leader=True)])),
             "side 1 has no starting leader"),
        ]
        for name, factory, message in cases:
            with self.subTest(case=name):
                with self.assertRaisesRegex(ValueError, message):
                    factory()

        with self.assertRaises(ValueError):
            LiteEngine('{"units":', _dumps(H.rules()))

    def test_unknown_recruit_is_rejected(self):
        game_spec = H.spec()
        game_spec["sides"][0]["recruit"] = ["Dragon"]
        with self.assertRaisesRegex(ValueError, "unknown recruit Dragon"):
            H.engine(game_spec=game_spec)


if __name__ == "__main__":
    unittest.main()
