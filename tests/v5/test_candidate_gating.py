"""T2: uncollected Astra seats skip full candidate generation.

The Rust extension is imported lazily, so this module still imports where the
lite engine has not been built. Timings are recorded for information only: no
speedup threshold is asserted here.
"""
from __future__ import annotations

import json
import unittest

from . import helpers

LEARNERS = {1, 3}


def _lite_engine():
    try:
        from _engine_lite import LiteEngine
    except ImportError as exc:  # pragma: no cover - depends on the local build
        raise unittest.SkipTest('Rust lite engine is not built: ' + str(exc))
    return LiteEngine


def _spec(*, max_turns=12, seed=7, separate_teams=False):
    spec = helpers.spec(sides=4, fog=False, seed=seed, max_turns=max_turns)
    for side in spec['sides']:
        side['gold'] = 0  # Reach the threat/movement planning paths without recruits.
        if separate_teams:
            side['team'] = str(side['id'])
    return spec


def _modules():
    from learning.lite_host import host_modules
    return host_modules()


def _counting_modules():
    """Wrap M.generate in a copy of the shipped Lua to count real C.generate runs."""
    modules = _modules()
    source = modules['candidates.lua']
    index = source.rindex('return M')
    wrapper = (
        'local _generate=M.generate\n'
        'function M.generate(obs)\n'
        '    local candidates,timing=_generate(obs)\n'
        '    timing.__generate_calls=(timing.__generate_calls or 0)+1\n'
        '    return candidates,timing\n'
        'end\n')
    modules['candidates.lua'] = source[:index] + wrapper + source[index:]
    return modules


def _engine(spec, modules=None):
    engine = _lite_engine()(json.dumps(helpers.rules()), json.dumps(spec))
    engine.configure_host(json.dumps(modules or _modules()))
    return engine


def _load(value):
    return json.loads(value)


def _without(dto, *dropped):
    value = dict(dto)
    for key in ('timing',) + dropped:
        value.pop(key, None)
    return value


def _teacher_action(dto):
    from learning.lite_host import teacher_candidate
    return teacher_candidate(dto['teacher_action'])


class CandidateGatingTests(unittest.TestCase):
    def test_lite_decision_fast_path_skips_full_generation(self):
        engine = _engine(_spec())
        before = _load(engine.snapshot())['game']
        full = _load(engine.decision(1, True, True))
        middle = _load(engine.snapshot())['game']
        fast = _load(engine.decision(1, True, False))
        after = _load(engine.snapshot())['game']
        self.assertEqual(before, middle)
        self.assertEqual(middle, after)
        self.assertEqual(full['timing']['budget'], 'work-12000-v5')
        self.assertGreater(len(full['candidates']), 1)
        self.assertNotIn('budget', fast['timing'])
        self.assertEqual(fast['timing'],
                         dict(truncated=False, ms=0, predictions=0, work=0))
        self.assertEqual([candidate['kind'] for candidate in fast['candidates']], ['end_turn'])
        self.assertEqual(full['teacher_action'], fast['teacher_action'])

    def test_uncollected_seats_never_call_generate(self):
        engine = _engine(_spec(), _counting_modules())
        seen = []
        for _ in range(12):
            view = _load(engine.observe(1))
            if view['finished']:
                break
            side = view['current_side']
            learner = side in LEARNERS
            decision = _load(engine.decision(side, True, learner))
            seen.append((side, learner, decision['timing'].get('__generate_calls')))
            outcome = _load(engine.execute_candidate(json.dumps(_teacher_action(decision))))
            self.assertTrue(outcome['committed'], outcome)
        uncollected = [row for row in seen if not row[1]]
        collected = [row for row in seen if row[1]]
        self.assertTrue(uncollected, seen)
        self.assertTrue(collected, seen)
        self.assertTrue(all(row[2] is None for row in uncollected), uncollected)
        self.assertEqual([row[2] for row in collected], [1] * len(collected))
        self.assertEqual(sum(row[2] or 0 for row in seen), len(collected))

    def test_candidates_only_seats_match_full_path(self):
        variants = (('team2v2', False, LEARNERS), ('ffa4', True, {1}))
        timings = []
        for label, separate_teams, learners in variants:
            with self.subTest(format=label):
                spec = _spec(separate_teams=separate_teams)
                full_engine = _engine(spec)
                gated_engine = _engine(spec)
                steps = 0
                learner_steps = uncollected_steps = 0
                finished = False
                for _ in range(12):
                    view = _load(full_engine.observe(1))
                    if view['finished']:
                        finished = True
                        break
                    side = view['current_side']
                    learner = side in learners
                    if learner:
                        learner_steps += 1
                    else:
                        uncollected_steps += 1
                    full = _load(full_engine.decision(side, True, True))
                    gated = _load(gated_engine.decision(side, True, learner))
                    timings.append((label, side, learner, full['timing']['ms'], gated['timing'].get('ms')))
                    self.assertEqual(full['teacher_action'], gated['teacher_action'])
                    self.assertEqual(full['reward_raw'], gated['reward_raw'])
                    if learner:
                        self.assertEqual(_without(full), _without(gated))
                        self.assertEqual(full['candidates'], gated['candidates'])
                    else:
                        # spatial.actions orders observed entities by candidate relevance,
                        # so only the unused DTO's entity order may differ.
                        self.assertEqual(_without(full, 'candidates', 'spatial'),
                                         _without(gated, 'candidates', 'spatial'))
                        self.assertEqual(full['spatial']['board'], gated['spatial']['board'])
                        self.assertEqual(sorted(full['spatial']['entities'], key=lambda e: e['id']),
                                         sorted(gated['spatial']['entities'], key=lambda e: e['id']))
                        self.assertEqual([c['kind'] for c in gated['candidates']], ['end_turn'])
                    action = _teacher_action(full)
                    self.assertEqual(action, _teacher_action(gated))
                    payload = json.dumps(action)
                    self.assertEqual(_load(full_engine.execute_candidate(payload))['committed'],
                                     _load(gated_engine.execute_candidate(payload))['committed'])
                    self.assertEqual(_load(full_engine.snapshot())['game'],
                                     _load(gated_engine.snapshot())['game'])
                    full_view = _load(full_engine.observe(side))
                    gated_view = _load(gated_engine.observe(side))
                    self.assertEqual(full_view['current_side'], gated_view['current_side'])
                    self.assertEqual(full_view['turn'], gated_view['turn'])
                    self.assertEqual(full_view['finished'], gated_view['finished'])
                    steps += 1
                self.assertGreater(learner_steps, 0, label)
                self.assertGreater(uncollected_steps, 0, label)
                self.assertTrue(steps == 12 or finished, (label, steps, finished))
        self.assertTrue(timings)


if __name__ == '__main__':
    unittest.main()
