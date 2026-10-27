"""Game-level splits, terminal rewards and on-policy advantages."""
import gzip
import hashlib
import json
from pathlib import Path
from functools import lru_cache
from .features import VERSION, GLOBAL, OPPONENT, ACTION, UNIT_TYPES, ENTITY, GEOMETRY, SPATIAL_CHANNELS
from .formats import infer_format, record_format
from .rowpack import ROW_SCHEMA, pack_line, row_meta


def split(game_id):
    return 'validation' if int(hashlib.sha256(game_id.encode()).hexdigest()[:8], 16) % 5 == 0 else 'train'


def record_split(row):
    """Read legacy run partitions or explicitly versioned scenario partitions."""
    rule = row.get('split_rule', 'family-seed-v1')
    if rule not in ('family-seed-v1', 'scenario-v2'):
        raise ValueError('unknown data split rule: ' + str(rule))
    key = row.get('scenario_family') if rule == 'scenario-v2' else row.get('game_family')
    if not isinstance(key, str) or not key:
        raise ValueError('sample lacks identity for ' + rule)
    return split(key)


def reward(result, side):
    from .rewards import terminal_rewards
    return terminal_rewards(result)[side]


@lru_cache(maxsize=1)
def _lite_teacher_source():
    # Source is frozen for the lifetime of a training process, not per row.
    from .teachers import source_digest
    return source_digest()


def validate_record(r, format_name=None):
    import math
    if r['schema'] not in (VERSION, ROW_SCHEMA) or len(r['global']) != len(GLOBAL):
        raise ValueError('feature schema mismatch')
    if r['schema'] == ROW_SCHEMA:
        if not math.isfinite(r.get('terminal_reward',float('nan'))):
            raise ValueError('row lacks finite terminal_reward')
        step = r.get('reward_step')
        if (step is None and r.get('source')=='policy') or (step is not None and not math.isfinite(step)):
            raise ValueError('row lacks finite reward_step')
    if not 1 <= len(r['candidates']) <= 128 or not 0 <= r['choice'] < len(r['candidates']):
        raise ValueError('invalid candidate/label')
    vectors = [r['global']] + list(r['opponents']) + [c['features'] for c in r['candidates']]
    if any(len(v) != len(OPPONENT) for v in r['opponents']) or any(len(c['features']) != len(ACTION) for c in r['candidates']):
        raise ValueError('feature width mismatch')
    if not all(math.isfinite(x) for v in vectors for x in v):
        raise ValueError('nonfinite features')
    spatial=r.get('spatial')
    if not spatial or len(spatial['entities'])>128 or len(spatial['board'])!=len(SPATIAL_CHANNELS):
        raise ValueError('current schema requires a legal spatial observation')
    for channel in spatial['board']:
        if len(channel)!=16 or any(len(row)!=16 or any(not math.isfinite(v) for v in row) for row in channel):
            raise ValueError('invalid public spatial grid')
    def entity(e):
        if len(e['features'])!=len(ENTITY) or not all(math.isfinite(v) for v in e['features']): raise ValueError('invalid entity features')
        if not isinstance(e['type_index'],int) or not 0<=e['type_index']<len(UNIT_TYPES): raise ValueError('invalid entity identity')
    for e in spatial['entities']: entity(e)
    for c in r['candidates']:
        if len(c.get('geometry',[]))!=len(GEOMETRY) or len(c.get('local',[]))!=19*len(SPATIAL_CHANNELS): raise ValueError('missing action geometry/neighborhood')
        if not all(math.isfinite(v) for part in (c.get('geometry', ()), c.get('local', ())) for v in part): raise ValueError('nonfinite action context')
        for key in ('actor','target'):
            if c.get(key): entity(c[key])
    if r.get('architecture_id')!='relational_v5' or not all(r.get(k) is not None for k in ('engine_id','rules_version','rng_version','combat_version','candidate_version','reward_version','reward_formula_id')):
        raise ValueError('sample lacks current-schema provenance')
    from .rewards import RewardConfig
    config=RewardConfig(**r['reward_config'])
    if config.reward_version!=r['reward_version'] or config.reward_formula_id!=r['reward_formula_id']:
        raise ValueError('sample reward version differs from frozen configuration')
    if r.get('source')=='policy':
        raw=r.get('reward_raw',{})
        if not all(k in raw and math.isfinite(raw[k]) for k in ('economy','control','explored')): raise ValueError('policy trajectory lacks raw reward terms')
        if not 0<=raw['explored']<=1: raise ValueError('invalid cumulative exploration')
    fmt=record_format(r)
    if format_name is not None and fmt != format_name: raise ValueError('cross-format sample rejected')
    if r.get('source') not in ('astra', 'stock_rca', 'human', 'policy'): raise ValueError('unknown data source')
    if r['source']=='stock_rca':
        from .manifest import active_teacher
        record=active_teacher(dict(teacher=r.get('teacher_identity')))
        if record['kind']!='wesnoth_default_rca' or r.get('teacher')!=record['kind']:
            raise ValueError('stock label has a different teacher identity')
        if r['engine_id'] not in ('native','native-1.18.8'):
            raise ValueError('stock teacher is native-only')
        if any(r.get(key)!=value for key,value in dict(teacher_profile='native',
                rng_version='native-1.18.8',combat_version='native-1.18.8').items()):
            raise ValueError('stock teacher engine/combat identity differs')
        if record.get('rules_sha256')!=r.get('rules_sha256',r['rules_version']):
            raise ValueError('stock teacher rules identity differs')
        if not record.get('capture_sha256') or r.get('teacher_source_sha256')!=record.get('runtime_sha256'):
            raise ValueError('stock teacher lacks capture/runtime provenance')
    if r.get('faults'): raise ValueError('faulted games cannot provide training samples')
    if r['source']=='astra':
        from .adapters import ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION
        from .teachers import PROFILE as TEACHER_PROFILE
        engine=r['engine_id']
        native=engine in ('native','native-1.18.8')
        if not native and engine not in ('lite',ENGINE_VERSION):
            raise ValueError('unknown Astra teacher engine identity')
        profile=r.get('teacher_profile')
        if (native and profile not in (None,'native')) or (not native and profile!=TEACHER_PROFILE):
            raise ValueError('sample was produced by a different Astra teacher profile')
        expected=dict(engine='native' if native else 'lite',engine_version='1.18.8' if native else ENGINE_VERSION,
                      rng_version='native-1.18.8' if native else RNG_VERSION,
                      combat_version='native-1.18.8' if native else COMBAT_VERSION)
        if any(r.get(key, value)!=value for key,value in expected.items()):
            raise ValueError('Astra teacher engine/combat identity differs')
        if r.get('teacher_source_sha256') is not None:
            source='native-1.18.8' if native else _lite_teacher_source()
            if r['teacher_source_sha256']!=source:
                raise ValueError('Astra teacher source identity differs')
    if r['source']=='astra' and r.get('teacher')!='gpt6astra': raise ValueError('only gpt6astra is an active teacher')
    if r['source']=='human':
        if r.get('human_control') is not True or r.get('native_version')!='1.18.8': raise ValueError('human sample lacks native/control provenance')
        if r.get('value_valid',False) and not r.get('result_verified'): raise ValueError('unknown human outcome cannot supervise value')
    if not r.get('version') or not r.get('game_family'): raise ValueError('sample lacks policy version/game family')
    expected = record_split(r)
    if r.get('split_rule') == 'scenario-v2' and r.get('split') is None:
        raise ValueError('scenario-v2 sample lacks explicit partition')
    if r.get('split') is not None and r['split'] != expected:
        raise ValueError('game family crosses data partitions')
    for candidate in r['candidates']:
        index=candidate['features'][-1]
        if int(index)!=index or not 0<=index<len(UNIT_TYPES): raise ValueError('invalid unit identity')
    if r.get('actual'):
        actual=r['actual'];candidate=r['candidates'][r['choice']]
        fields=dict(end_turn=[],recruit=['type','x','y'],move=['x','y','tx','ty','full'],
            attack=['x','y','tx','ty','weapon'],move_attack=['x','y','tx','ty','ex','ey','weapon'])
        if candidate['kind']!=actual['kind'] or any(candidate.get(k)!=actual.get(k) for k in fields[actual['kind']]):
            raise ValueError('label does not exactly match executed action intent')


def write_shard(path, game_id, records, result, bootstraps=None, provenance=None):
    from .rewards import row_transition
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written=raw_count=0;bootstraps=bootstraps or {}
    excluded='faulted_game' if result.get('faults') else None
    def is_truncated(side):
        if result.get('reason')!='turn_limit':return False
        survivors=result.get('survivors')
        if survivors is None:return True
        if result.get('teams'):return any(result['teams'][s-1]==result['teams'][side-1] for s in survivors)
        return side in survivors
    steps, pending = {}, {}
    outcomes = {side:reward(result,side) for side in range(1,len(result['bots'])+1)} if not excluded else {}
    def step_value(row, following=None):
        if not row.get('reward_raw') or (following is None and row.get('truncated') and not row.get('bootstrap_raw')):
            return None  # Unsupplied teacher/human reward evidence is explicitly unknown.
        return row_transition(row,following)[0]
    for index,r in enumerate(records):
        if is_truncated(r['side']) and r.get('source')=='policy' and str(r['side']) not in bootstraps:
            excluded='missing_truncation_bootstrap'
        if not excluded:
            side=r['side'];bootstrap=bootstraps.get(str(side),{})
            terms=dict(provenance or {},**{key:r[key] for key in
                ('turn','reward_raw','reward_after','reward_config') if key in r})
            terms={key:terms[key] for key in ('turn','reward_raw','reward_after','reward_config') if key in terms}
            terms.update(schema=ROW_SCHEMA,terminal_reward=outcomes[side],truncated=is_truncated(side),
                         bootstrap_raw=bootstrap.get('reward_raw'),bootstrap_turn=bootstrap.get('turn'))
            if side in pending:
                previous,context=pending[side]
                steps[previous]=step_value(context,terms)
            pending[side]=(index,terms)
    if not excluded:
        for index,context in pending.values(): steps[index]=step_value(context)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        if excluded:return dict(written=0,excluded=excluded)
        def augmented():
            nonlocal written, raw_count
            for index,r in enumerate(records):
                r = dict(provenance or {}, **r)
                family=r.get('game_family', game_id)
                truncated=is_truncated(r['side'])
                bootstrap=bootstraps.get(str(r['side']),{})
                r.update(game_family=family, split_rule=r.get('split_rule', 'family-seed-v1'))
                r.pop('reward',None)
                r = dict(r, schema=ROW_SCHEMA, game_id=game_id, game_family=family, split=record_split(r),
                         terminal_reward=outcomes[r['side']],reward_step=steps[index],value_valid=r.get('value_valid',True) and not truncated,
                         truncated=truncated,bootstrap_value=bootstrap.get('value'),bootstrap_potential=bootstrap.get('potential'),
                         bootstrap_raw=bootstrap.get('reward_raw'),bootstrap_turn=bootstrap.get('turn'),
                         players=len(result['bots']), format=infer_format(result), faults=result['faults'],
                         faction=result.get('factions',[None]*len(result['bots']))[r['side']-1])
                r.setdefault('source', 'astra' if r.get('teacher') else 'policy')
                if r.get('choice',-1)>=0: validate_record(r);written+=1
                f.write(pack_line(r) + '\n')
                raw_count += 1
                yield r
        from .sequences import IndexedSequenceStore
        with IndexedSequenceStore(path.parent/'sequences') as store: store.write(augmented())
    return dict(written=written,raw_records=raw_count,excluded=None)


@lru_cache(maxsize=8192)
def _shard_identity(path, size, modified):
    """Production shards contain one format/source/family/partition per file."""
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            r=row_meta(line)
            if not r.get('faults'):return r['format'],r['source'],r['split'],r['game_family'],r.get('engine_id',r.get('engine'))
    return None


def read_shards(paths, partition=None, limit=None, seed=19, format_name=None, **options):
    """Read complete raw prefixes before limiting supervised sequence windows."""
    from .sequences import read_shards as read_sequences
    return read_sequences(paths, partition=partition, limit=limit, seed=seed, format_name=format_name, **options)


def bc_sample(records, count, rng=None):
    """Compatibility wrapper; training loops should reuse make_bc_sampler once."""
    sampler = records if isinstance(records, BCSampler) else make_bc_sampler(records)
    return sampler.sample(count, rng=rng)


class BCSampler:
    """Reusable pool/source/engine/family index, built once per data refresh."""
    def __init__(self, records, allow_policy=False, *, exclude_teacher_impl=None, exclude_teacher_sha=None):
        from collections import defaultdict
        from .sequences import attach_histories
        rows = list(records)
        if not all('_history' in r for r in rows):
            rows = attach_histories(rows)
        self.pools = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
        sources = ('astra', 'stock_rca', 'human', 'policy') if allow_policy else ('astra', 'stock_rca', 'human')
        self.rows_excluded = 0
        identities = set()
        for row in rows:
            if row.get('split') != 'train' or row.get('source') not in sources or row.get('choice', -1) < 0 or row.get('faults'):
                continue
            teacher_label = row['source'] not in ('human', 'policy')
            impl = (row.get('teacher') or row.get('teacher_impl')) if teacher_label else None
            sha = row.get('teacher_source_sha256') if teacher_label else row.get('policy_sha256')
            excluded = (teacher_label and exclude_teacher_impl is not None and
                        exclude_teacher_impl in (row.get('teacher'), row.get('teacher_impl')))
            if excluded or (exclude_teacher_sha is not None and sha == exclude_teacher_sha):
                self.rows_excluded += 1
                continue
            pool = row.get('data_pool', row.get('data_role'))
            if pool is None:
                pool = 'dagger' if row.get('dagger') or row.get('teacher_query') else 'original'
            if pool not in ('original', 'dagger'):
                raise ValueError('unknown BC data pool')
            engine = row.get('engine_id', row.get('engine'))
            if engine is None:
                raise ValueError('BC requires explicit native/lite engine provenance')
            self.pools[pool][row['source']][engine][row['game_family']].append(row)
            identities.add((row['source'], impl or '', sha or ''))
        if not self.pools:
            if exclude_teacher_impl is not None or exclude_teacher_sha is not None:
                raise ValueError('no rehearsal data distinct from the evaluation control')
            raise ValueError('BC requires Astra or compatible human training games')
        self.source_identities = [dict(source=source,teacher_impl=impl or None,sha256=sha or None)
                                  for source,impl,sha in sorted(identities)]
        # Freeze all selection keys once. Minibatches only index these lists.
        self.pool_keys = tuple(sorted(self.pools))
        self.source_keys = {p: tuple(sorted(sources)) for p, sources in self.pools.items()}
        self.engine_keys = {(p, s): tuple(sorted(engines)) for p, sources in self.pools.items() for s, engines in sources.items()}
        self.family_keys = {(p, s, e): tuple(sorted(families)) for p, sources in self.pools.items() for s, engines in sources.items() for e, families in engines.items()}

    def sample(self, count, rng=None):
        import random
        rng = rng or random
        if count < 1:
            raise ValueError('BC sample count must be positive')
        result = []
        for _ in range(count):
            pool = rng.choice(self.pool_keys)  # 50/50 original/DAgger when both exist
            sources = self.source_keys[pool]
            teacher = next((source for source in sources if source in ('astra','stock_rca')),None)
            source = ('human' if rng.random() < .25 else teacher) if teacher and set(sources)=={teacher,'human'} else rng.choice(sources)
            engines = self.engine_keys[(pool, source)]
            # Original native anchors get 50% when both engines exist (>=25%).
            # Versioned native engines remain isolated as separate sampling keys.
            native = tuple(e for e in engines if e.startswith('native'))
            other = tuple(e for e in engines if not e.startswith('native'))
            engine = rng.choice(native if rng.random() < .5 else other) if native and other else rng.choice(engines)
            family = rng.choice(self.family_keys[(pool, source, engine)])
            result.append(rng.choice(self.pools[pool][source][engine][family]))
        return result


def make_bc_sampler(records, allow_policy=False, *, exclude_teacher_impl=None, exclude_teacher_sha=None):
    return BCSampler(records, allow_policy=allow_policy,exclude_teacher_impl=exclude_teacher_impl,
                     exclude_teacher_sha=exclude_teacher_sha)


def advantages(records, gamma=None, lam=None, shaping_weight=None):
    import math
    from .rewards import row_transition
    groups = {}
    for i, r in enumerate(records):
        groups.setdefault((r['game_id'], r['side']), []).append(i)
    adv, returns = [0.] * len(records), [0.] * len(records)
    for indices in groups.values():
        indices.sort(key=lambda i:(records[i]['turn'],records[i].get('decision',i)))
        last=records[indices[-1]]
        discount_gamma=last['reward_config']['gamma'] if gamma is None else gamma
        gae_lambda=last['reward_config']['gae_lambda'] if lam is None else lam
        if last.get('truncated') and last.get('bootstrap_value') is None:
            raise ValueError('truncated PPO trajectory requires a bootstrap value')
        gae, next_value = 0., last['bootstrap_value'] if last.get('truncated') else 0.
        for t, i in reversed(list(enumerate(indices))):
            r = records[i]
            following=records[indices[t+1]] if t+1<len(indices) else None
            immediate,turns=row_transition(r,following,gamma=discount_gamma)
            if r.get('reward_step') is not None and not math.isclose(r['reward_step'],immediate,rel_tol=0.,abs_tol=1e-9):
                raise ValueError('reward_step differs from transition_reward')
            discount=discount_gamma**turns
            delta = immediate + discount * next_value - r['value']
            gae = delta + discount * gae_lambda**turns * gae
            adv[i], returns[i] = gae, gae + r['value']
            next_value = r['value']
    return adv, returns
