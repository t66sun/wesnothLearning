"""Native and lite boundaries; snapshots remain internal to training/differentials."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol, Any

ROOT = Path(__file__).resolve().parents[1]

# Identity of the Rust engine build this adapter speaks to. The build itself is
# cross-checked in LiteAdapter so a stale extension can never write new rows.
ENGINE_VERSION = 'lite-0.2'
RNG_VERSION = 'deterministic-expected_damage_v1'
COMBAT_VERSION = 'expected_damage_v1'


class GameAdapter(Protocol):
    engine_id: str
    def reset(self, game_spec: dict) -> Any: ...
    def close(self) -> None: ...

    def observe(self, side: int) -> dict: ...
    def legal_actions(self, side: int) -> list[dict]: ...
    def step(self, action: dict) -> dict: ...
    def snapshot(self) -> dict: ...
    def restore(self, snapshot: dict) -> None: ...


class NativeAdapter:
    """Persistent original game. Native snapshots restart and replay the full log."""
    engine_id = 'native-1.18.8'
    rng_version = 'native-1.18.8'
    combat_version = 'native-1.18.8'

    def __init__(self, game_spec=None, transport=None, **kwargs):
        if transport is None:
            from .native_transport import NativeTransport
            transport=NativeTransport(game_spec,**kwargs)
        self.transport = transport

    def reset(self, game_spec): return self.transport.reset(game_spec)
    def close(self): return self.transport.close()
    def decision(self, side, **kwargs): return self.transport.decision(side,**kwargs)
    def execute_candidate(self, action): return self.transport.execute_candidate(action)

    def observe(self, side):
        return self.transport.observe(side)

    def legal_actions(self, side):
        return self.transport.legal_actions(side)

    def step(self, action):
        return self.transport.step(action)

    def snapshot(self):
        return self.transport.snapshot()

    def restore(self, snapshot):
        self.transport.restore(snapshot)


class LiteAdapter:
    engine_id = ENGINE_VERSION
    rng_version = RNG_VERSION
    combat_version = COMBAT_VERSION

    def __init__(self, game_spec, rules_dir=None, *, require_accepted=True):
        from .rules_catalog import load as load_catalog, resolve_dir
        rules_dir = resolve_dir(rules_dir)
        catalog = load_catalog(rules_dir, require_accepted=require_accepted)
        self.catalog = catalog
        raw_rules = (rules_dir / 'rules.json').read_bytes()
        digest = hashlib.sha256(raw_rules).hexdigest()
        if digest != catalog.get('rules_file_sha256'):
            raise ValueError('rules.json differs from the frozen catalog hash')
        rules = json.loads(raw_rules)
        if rules['source_hash'] != catalog['source_hash']:
            raise ValueError('catalog/rules source provenance mismatch')
        if rules['source_version'] != '1.18.8':
            raise ValueError('lite requires native 1.18.8 data')
        modifier=game_spec.get('experience_modifier',100)
        if not isinstance(modifier,int) or modifier<1: raise ValueError('invalid experience modifier')
        for unit in rules['units'].values(): unit['experience']=max(1,(unit['experience']*modifier+50)//100)
        try:
            import _engine_lite
            from _engine_lite import LiteEngine
        except ImportError as exc:
            raise RuntimeError('Rust extension is not built: install Rust, then build engine_lite with maturin') from exc
        built = tuple(getattr(_engine_lite, key, None)
                      for key in ('ENGINE_VERSION', 'RNG_VERSION', 'COMBAT_VERSION'))
        declared = (ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION)
        if built != declared:
            raise RuntimeError('engine_lite build identity %s does not match the declared %s; '
                               'rebuild the extension with maturin develop' % (built, declared))
        self.spec = dict(game_spec)
        self.rules_sha256 = digest
        self.core = LiteEngine(json.dumps(rules), json.dumps(game_spec))

    def reset(self, game_spec):
        self.spec = dict(game_spec)
        self.core.reset(json.dumps(game_spec))
        # Rust reset creates a new Lua VM and reinstalls its saved modules.

    def close(self): self.core=None

    def observe(self, side):
        return json.loads(self.core.observe(side))

    def observe_batch(self, sides):
        return json.loads(self.core.observe_batch(json.dumps(list(sides))))

    def legal_actions(self, side):
        return json.loads(self.core.legal_actions(side))

    def legal_batch(self, sides):
        return json.loads(self.core.legal_batch(json.dumps(list(sides))))

    def step(self, action):
        return json.loads(self.core.step(json.dumps(action)))

    def step_batch(self, actions):
        return json.loads(self.core.step_batch(json.dumps(list(actions))))

    def snapshot(self):
        return json.loads(self.core.snapshot())

    def restore(self, snapshot):
        self.core.restore(json.dumps(snapshot))

    def forecast(self, side, attacker, target, weapon, samples=128):
        # `samples` is kept for callers that still pass it; the resolver is
        # deterministic, so the value is ignored by the engine.
        return json.loads(self.core.forecast(side, attacker, target, weapon, samples))

    def configure_host(self, modules):
        self.modules=modules
        self.core.configure_host(json.dumps(modules))

    def decision(self, side, *, budget_ms=500, teacher=False, generate_candidates=True):
        return json.loads(self.core.decision(side, budget_ms, teacher, generate_candidates))

    def execute_candidate(self, action):
        return json.loads(self.core.execute_candidate(json.dumps(action)))


def create_adapter(engine, game_spec=None, **kwargs) -> GameAdapter:
    if engine == 'native':
        return NativeAdapter(game_spec,**kwargs)
    if engine == 'lite':
        return LiteAdapter(game_spec, **kwargs)
    raise ValueError(f'unknown engine {engine!r}')


NativeWesnothAdapter=NativeAdapter
LiteWesnothAdapter=LiteAdapter
