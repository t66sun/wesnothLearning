"""Persistent direct Rust/Lua collection using the shared native Lua modules.

Only explicit game specs can be collected: this layer never fabricates standard
era factions, leader definitions or frozen maps from incomplete local data.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .adapters import COMBAT_VERSION, ENGINE_VERSION, LiteAdapter, RNG_VERSION, ROOT
from .rowpack import compact_row
from .trajectory_buffer import TrajectoryBuffer


def _lua(value):
    if value is None:
        return 'nil'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('nonfinite Lua schema value')
        return repr(value)
    if isinstance(value, str):
        # JSON is not Lua string escaping (notably \u and surrogate pairs).
        return '"' + ''.join('\\' + c if c in '\\"' else '\\%03d' % ord(c)
                             if ord(c) < 32 else c for c in value) + '"'
    if isinstance(value, dict):
        return '{' + ','.join('[' + _lua(k) + ']=' + _lua(v) for k, v in value.items()) + '}'
    return '{' + ','.join(_lua(v) for v in value) + '}'


def host_modules(teacher_path=None):
    from .features import schema
    from .teachers import lua_modules
    modules = {name: (ROOT / 'lua' / name).read_text(encoding='utf-8')
               for name in ('observation.lua', 'candidates.lua', 'spatial.lua', 'routing.lua', 'rewards.lua')}
    modules['features.lua'] = 'return ' + _lua(schema())
    # The frozen archive remains lineage only; the host runs the maintained
    # derived source adapted to expected_damage_v1.
    if teacher_path is not None:
        from .lite_policy import is_astra
        if not is_astra(teacher_path): raise ValueError('unknown explicit legacy Lite teacher')
        modules.update(lua_modules())
    return modules


class LiteHost:
    def __init__(self, game_spec, rules_dir=None, *, require_accepted=True, teacher_path=None):
        self.adapter = LiteAdapter(game_spec, rules_dir, require_accepted=require_accepted)
        from .features import schema
        if schema()['rules_sha256'] != self.adapter.rules_sha256:
            raise ValueError('shared feature vocabulary is frozen from another rules catalog')
        self.modules = host_modules(teacher_path)
        self.adapter.configure_host(self.modules)

    def reset(self, game_spec):
        self.adapter.reset(game_spec)

    def decision(self, side, *, teacher=False, budget_ms=500, generate_candidates=True):
        return self.adapter.decision(side, teacher=teacher, budget_ms=budget_ms,
                                     generate_candidates=generate_candidates)

    def execute(self, action):
        return self.adapter.execute_candidate(action)

    def snapshot(self):
        return self.adapter.snapshot()

    def restore(self, snapshot):
        self.adapter.restore(snapshot)


def teacher_candidate(plan):
    """Translate Astra's original intent without adding it to student candidates."""
    kind = plan['kind']
    if kind == 'combat':
        if plan['x'] == plan['tx'] and plan['y'] == plan['ty']:
            return dict(kind='attack', x=plan['x'], y=plan['y'], tx=plan['ex'], ty=plan['ey'], weapon=plan['weapon'])
        return dict(kind='move_attack', x=plan['x'], y=plan['y'], tx=plan['tx'], ty=plan['ty'],
                    ex=plan['ex'], ey=plan['ey'], weapon=plan['weapon'])
    if kind == 'move':
        return dict(kind='move', x=plan['x'], y=plan['y'], tx=plan['tx'], ty=plan['ty'], full=True)
    if kind in ('recruit', 'end_turn'):
        return {k: v for k, v in plan.items() if k in ('kind', 'type', 'x', 'y')}
    raise ValueError(f'unsupported Astra intent {kind}')


def _matching(candidates, action):
    fields = {'end_turn': (), 'move': ('x', 'y', 'tx', 'ty', 'full'),
              'attack': ('x', 'y', 'tx', 'ty', 'weapon'),
              'move_attack': ('x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon'),
              'recruit': ('type', 'x', 'y')}
    for i, candidate in enumerate(candidates):
        if candidate['kind'] == action['kind'] and all(candidate.get(k) == action.get(k) for k in fields[action['kind']]):
            return i
    return -1


def play_lite_job(job):
    """Play one accepted-lite Astra or explicit policy job; never fallback native.

    policy callbacks receive only the common decision DTO. Official baseline is
    unsupported in lite. No hidden true state enters Astra or policy callbacks.
    """
    from .features import schema
    from .data import write_shard
    from .rewards import RewardConfig
    from .teachers import identity as teacher_identity
    from .lite_policy import FrozenPolicies,game_spec,is_astra
    from .reward_metrics import summarize_game
    job_id = job['id']
    records, dagger = TrajectoryBuffer(), TrajectoryBuffer()
    try:
        if time.time() >= job.get('deadline', float('inf')):
            return dict(id=job_id, status='budget_interrupted', engine='lite')
        record=job.get('teacher_identity',{})
        learning=job.get('learning',{})
        requested=any(side.get('teacher') for side in learning.get('sides',{}).values()) or learning.get('dagger_teacher')
        if record.get('kind')=='wesnoth_default_rca' and requested:
            raise ValueError('stock RCA teacher is native-only')
        legacy=any(is_astra(bot) for bot in job.get('bots',[])) or is_astra(learning.get('dagger_teacher') or '')
        if legacy and record.get('kind')!='gpt6astra':
            raise ValueError('Astra jobs require an explicit legacy teacher identity')
        if 'game_spec' not in job:
            from .rules_catalog import resolve_dir
            rules_dir=resolve_dir(job.get('rules_dir'))
            rules=json.loads((rules_dir/'rules.json').read_text(encoding='utf-8'))
            job=dict(job,game_spec=game_spec(job,rules))
        bots = job.get('bots', [])
        policy = job.get('policy')
        if any(bot=='baseline' for bot in bots): raise ValueError('official baseline is native-only')
        policies=FrozenPolicies(job) if policy is None else None
        teacher_paths = list(bots) + [job.get('learning', {}).get('dagger_teacher')]
        teacher_path = next((Path(p) for p in teacher_paths
                             if isinstance(p, (str, Path)) and is_astra(p)
                             and Path(p).suffix == '.zip'), None)
        host = LiteHost(job['game_spec'], job.get('rules_dir'),
                        require_accepted=job.get('require_accepted', True), teacher_path=teacher_path)
        teacher_profile=teacher_identity()['teacher_profile'] if legacy else 'none'
        behavior, bootstraps, metric_snapshots = [], {}, []
        config = job.get('reward_config') or RewardConfig().to_dict()
        config = RewardConfig(**config).to_dict()
        rank_points, defeated = {}, set()
        decision_count = 0
        current = 1
        learning=job.get('learning',{}).get('sides',{})
        learner_sides=set(map(int,learning)) if learning else set(job.get('learner_sides',[]))
        def metric_snapshot(side,event):
            row=host.decision(side,teacher=False,generate_candidates=False)
            snapshot={k:row[k] for k in ('side','turn','global','spatial','reward_raw')}
            snapshot.update(metric_event=event,source='astra' if is_astra(bots[side-1]) else 'policy',
                            teacher='gpt6astra' if is_astra(bots[side-1]) else False,
                            rules_version=host.adapter.catalog['rules_version'],
                            engine_version=ENGINE_VERSION, combat_version=COMBAT_VERSION,
                            teacher_profile=teacher_profile)
            metric_snapshots.append(snapshot)
        for side in sorted(learner_sides):
            metric_snapshot(side,'initial')
        query_count={};side_decisions={};query_total=0
        while True:
            view = host.adapter.observe(current)
            if view['finished']:
                break
            current = view['current_side']
            if time.time() >= job.get('deadline', float('inf')):
                return dict(id=job_id, status='budget_interrupted', engine='lite')
            if decision_count >= job.get('max_decisions', 100000):
                raise RuntimeError('lite decision budget exhausted; no progress/teacher loop must be diagnosed')
            decision_count += 1
            teacher=is_astra(bots[current-1]) if policies else False
            side_decisions[current]=side_decisions.get(current,0)+1
            query=not teacher and current in learner_sides and job.get('learning',{}).get('dagger_teacher') and side_decisions[current]%4==0 and query_total<32
            # Unrecorded Astra seats need their plan, not student candidates.
            # Policy seats (including DAgger queries) always need the full set.
            decision = host.decision(current, teacher=teacher or bool(query),
                                     generate_candidates=not teacher or current in learner_sides)
            training=learning.get(str(current),{})
            decision.update(schema=schema()['version'], format=job.get('format', job.get('meta', {}).get('format')),
                            source='astra' if teacher else 'policy', engine_id='lite',
                            rules_version=host.adapter.catalog['rules_version'],
                            rules_sha256=host.adapter.rules_sha256, rng_version=RNG_VERSION,
                            combat_version=COMBAT_VERSION, teacher_profile=teacher_profile,
                            version=training.get('version','teacher-frozen' if teacher else 'v5-validation'),decision=decision_count,
                            architecture_id='relational_v5', candidate_version=f"schema{schema()['version']}-"+decision['timing'].get('budget','fixed-20000-v1'),
                            engine='lite', engine_version=ENGINE_VERSION,
                            teacher_impl='astra_lite' if teacher else None,
                            teammate_context=job.get('meta',{}).get('context','astra_partner' if job.get('teams') else 'solo'),
                            data_pool=job.get('data_pool', 'original'),
                            reward_config=config, reward_version=config['reward_version'],
                            map=job.get('meta',{}).get('map'),map_sha256=job.get('meta',{}).get('map_sha256'),map_partition=job.get('meta',{}).get('map_partition'),
                            reward_formula_id=config['reward_formula_id'], game_family=job.get('game_family', job_id),
                            scenario_family=job.get('scenario_family'), split_rule=job.get('split_rule', 'family-seed-v1'))
            teacher_plan=decision.pop('teacher_action',None)
            if teacher:
                action = teacher_candidate(teacher_plan)
                choice = _matching(decision['candidates'], action)
                decision.update(choice=choice, log_probability=0., value=0., teacher='gpt6astra',
                                actual=action, intent=action, representable=True)
            else:
                # Judge scalars supervise value/reward only. The actor receives
                # exactly the public common Lua observation and candidates.
                actor_input = {k: v for k, v in decision.items() if k not in ('reward_raw', 'reward_after', 'teacher_action')}
                selected = policies.choose(actor_input,current) if policies else policy(actor_input)
                choice = int(selected['choice'])
                if not 0 <= choice < len(decision['candidates']):
                    raise ValueError('policy returned an invalid candidate index')
                action = decision['candidates'][choice]
                decision.update(choice=choice, log_probability=float(selected['log_probability']),
                                value=float(selected['value']), actual=action, intent=action)
            outcome = host.execute(action)
            decision['outcome'] = outcome['events']
            decision['diagnostics'] = outcome['diagnostics']
            decision['reward_after'] = outcome['reward_after']
            decision['committed']=outcome['committed']
            if outcome.get('memory_write'): decision['memory_write']=dict(outcome['memory_write'],turn=decision['turn'])
            if policies and not teacher: policies.commit(current,decision,outcome)
            behavior.append(outcome['diagnostics'])
            if current in learner_sides:
                decision = compact_row(decision)
                records.append(decision)
                if not teacher and job.get('learning',{}).get('dagger_teacher'):
                    label=dict(decision,source='astra',teacher='gpt6astra',teacher_impl='astra_lite',choice=-1,value_valid=False,data_pool='dagger')
                    if query:
                        query_count[current]=query_count.get(current,0)+1;query_total+=1
                        wanted=teacher_candidate(teacher_plan);label.update(actual=wanted,intent=wanted,choice=_matching(decision['candidates'],wanted),query_only=True)
                    dagger.append(label)
            view = outcome['view'];current = view['current_side']
            newly = {s['id'] for s in view['sides'] if s['eliminated']} - defeated
            if newly:
                points = len(defeated) + (len(newly)-1)/2
                rank_points.update({str(s): points for s in newly});defeated.update(newly)
                for side in sorted(newly & learner_sides):
                    metric_snapshot(side,'eliminated')
            if view['finished']:
                break
        if view['truncated'] and any(not is_astra(bots[side-1]) for side in learner_sides):
            # Never replace missing truncation values with zero or a teacher score.
            bootstrap_policy = job.get('bootstrap_policy')
            if bootstrap_policy is None and policies is None:
                raise RuntimeError('truncated policy game requires a frozen bootstrap_policy callback')
            for side in learner_sides:
                if is_astra(bots[side-1]): continue
                decision = host.decision(side, teacher=False)
                actor_input = {k: v for k, v in decision.items() if k not in ('reward_raw', 'reward_after', 'teacher_action')}
                bootstraps[str(side)] = dict(side=side, value=policies.choose(actor_input,side,bootstrap=True) if policies else float(bootstrap_policy(actor_input)),
                                             potential=decision['potential'], reward_raw=decision['reward_raw'], turn=decision['turn'],
                                             version=job.get('learning', {}).get('version', 'v5-validation'))
        survivors = [s['id'] for s in view['sides'] if not s['eliminated']]
        if not view['truncated']:
            for side in sorted(learner_sides-set(defeated)):
                metric_snapshot(side,'terminal')
        points = len(defeated) + (len(survivors)-1)/2
        rank_points.update({str(s): points for s in survivors})
        teams = [s['team'] for s in job['game_spec']['sides']]
        winning_sides = [s['id'] for s in view['sides'] if s['team'] == view['winner']]
        result = dict(engine_id=ENGINE_VERSION, rng_version=RNG_VERSION, combat_version=COMBAT_VERSION,
                      winner=winning_sides[0] if len(winning_sides)==1 else 0,
                      winning_team=view['winner'] or 0, truncated=view['truncated'],
                      reason='turn_limit' if view['truncated'] else 'victory', survivors=survivors,
                      bots=bots or ['gpt6astra']*len(teams), factions=job.get('factions') or [None]*len(teams), teams=teams if len(set(teams))<len(teams) else None,
                      turns=view['turn'], faults=[], rank_points=rank_points, approximate=True)
        written = write_shard(job['shard'], job_id, records, result, bootstraps) if job.get('shard') else None
        if dagger and job.get('shard'):
            path=Path(job['shard']);write_shard(path.with_name(path.name.replace('.jsonl.gz','.dagger.jsonl.gz')),job_id,dagger,result,bootstraps)
        coverage = records.coverage
        return dict(id=job_id, status='complete', engine='lite', result=result, coverage=coverage,
                    reward_diagnostics=summarize_game(records.metric_rows(),result,job,snapshots=metric_snapshots),
                    training_eligible=written is None or bool(written['written']), training_shard=written,
                    behavior=behavior, meta=job.get('meta', {}),
                    truncated=records.truncated)
    except (RuntimeError, ValueError, ImportError, OSError, KeyError) as exc:
        return dict(id=job_id, status='infrastructure_error', engine='lite', error=str(exc))
    finally:
        records.close()
        dagger.close()
