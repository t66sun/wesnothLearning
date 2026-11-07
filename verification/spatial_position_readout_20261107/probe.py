"""Replay fixed public states and the recorded duel sequence without optimizer updates."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import torch

from learning.bc import auxiliary_loss
from learning.bc_anchor import weights_sha256
from learning.common import ROOT, read_json, sha256, write_json
from learning.coordinator import Experiment
from learning.experiment import FormatExperiment, default_config
from learning.export import load_model, verify_numerics
from learning.lite_host import LiteHost
from learning.lite_policy import FrozenPolicies
from learning.model import ARCHITECTURE, batch
from learning.sequence_parity import _ParityAudit
from learning.sequences import read_raw_shards


def initialized_runner(parent, directory, rules):
    checkpoint = parent / 'duel/last_bc.pt'
    checkpoint_hash = '05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab'
    manifest_hash = '6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88'
    assert sha256(checkpoint) == checkpoint_hash
    assert sha256(parent / 'manifest.json') == manifest_hash
    config = default_config('cpu', engine='lite') | dict(
        phase='bc', formats=['duel'], trainer_threads=1, seed=202611060,
        rules_dir=str(rules), human_data=str(directory.parent / 'empty'),
        branch_weights_only=True, branch_checkpoint='last_bc', allow_approximate=True)
    run = Experiment(directory, config=config, branch_from=parent)

    def collect(*args):
        raise AssertionError('readout verification must not collect')

    runner = FormatExperiment(directory/'duel', 'duel', run.manifest, run.clock, collect, branch=True)
    assert sha256(checkpoint) == checkpoint_hash
    source = torch.load(checkpoint, map_location='cpu', weights_only=False)['model']
    current = runner.model.state_dict()
    actor = {k: v for k, v in current.items() if k in source and not k.startswith('value.')}
    assert set(actor) == {k for k in source if not k.startswith('value.')}
    assert all(torch.equal(source[k], v) for k, v in actor.items())
    assert not runner.optimizer.state and not runner.state['effective']
    assert not any(runner.state[k] for k in ('teacher_shards', 'dagger_shards', 'policy_shards', 'history'))
    return runner, dict(checkpoint_sha256=checkpoint_hash, manifest_sha256=manifest_hash,
                        common_actor_sha256=weights_sha256(actor),
                        reset_value_sha256=weights_sha256({k: v for k, v in current.items() if k.startswith('value.')}))


def measure(action, setup=lambda: None):
    for i in range(3):
        setup()
        start = perf_counter()
        decision = action()
        if i == 0:
            times = []
        else:
            times.append((perf_counter() - start) * 1000)
    return times, decision


def training_times(model, row):
    times = []
    rows = [row]
    target = torch.tensor([row['choice']])
    for i in range(3):
        model.zero_grad(set_to_none=True)
        start = perf_counter()
        logits, value = model(*batch(rows, history_cache={}))
        distribution = torch.distributions.Categorical(logits=logits)
        loss = -distribution.log_prob(target).mean() + .1 * auxiliary_loss(logits, rows)
        loss = loss + .5 * (value - .5).square().mean()
        mid = perf_counter()
        loss.backward()
        end = perf_counter()
        if i:
            times.append(dict(forward_ms=(mid - start)*1000, backward_ms=(end - mid)*1000,
                              total_ms=(end - start)*1000))
    assert torch.isfinite(loss)
    return times


def lua_decision(audit, row):
    lua, network, weights = audit.lua, audit.network, audit.weights
    memory = lua.table()

    def inputs(item, candidates):
        return (*(lua.table_from(item[key], recursive=True) for key in ('global', 'opponents')),
                candidates, lua.table_from(item['spatial'], recursive=True), memory, item['turn'])

    for write in row.get('_history', []):
        _, _, pending = network.forward(weights, *inputs(write, lua.table()))
        network.commit(memory, pending)
    args = inputs(row, lua.table_from(row['candidates'], recursive=True))

    def choose():
        scores, value, _ = network.forward(weights, *args)
        choice, logp = network.choose(scores, False)
        return dict(choice=choice-1, log_probability=logp, value=value)

    return choose


def timings(runner, cases, long):
    model = runner.model
    policies = FrozenPolicies(dict(format='duel', bots=[runner.support, 'gpt6astra'], seed=228))
    audit = _ParityAudit(model)
    results = {}
    for name, row, host in [*cases, ('recorded_long', long, None)]:
        history = row.get('_history', [])
        policies.histories[1] = history[:-1]
        policies.memory_contexts.clear()
        policies.memory_states.clear()
        if history:
            policies.choose(row, 1)  # Prime the saved prefix before the most recent commit.
        memory_states, contexts = policies.memory_states.copy(), policies.memory_contexts.copy()

        def restore():
            policies.histories[1] = history
            policies.memory_states = memory_states.copy()
            policies.memory_contexts = contexts.copy()

        decision, choice = measure(lambda: policies.choose(host.decision(1) if host else row, 1), restore)
        lua, lua_choice = measure(lua_decision(audit, row))
        assert choice['choice'] == lua_choice['choice']
        assert abs(choice['value'] - lua_choice['value']) < 1e-5
        assert abs(choice['log_probability'] - lua_choice['log_probability']) < 1e-5
        results[name] = dict(candidates=len(row['candidates']), entities=len(row['spatial']['entities']),
                             turn=row['turn'], history=len(history), lite_ms=decision, lua_ms=lua,
                             training=training_times(model, row), decision=choice)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('rules', type=Path)
    parser.add_argument('shard', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    assert not args.output.exists()
    with TemporaryDirectory(dir=ROOT, prefix='position-readout-') as temporary:
        runner, initializer = initialized_runner(args.parent, Path(temporary)/'child', args.rules)
        records = read_raw_shards([args.shard], 'duel')
        assert len({(r['game_id'], r['side']) for r in records}) == 1
        long = next(r for r in records if r['turn'] == records[-1]['turn'] and len(r['candidates']) == 37)
        assert len(long['_history']) >= 16
        fixture = ROOT / 'verification/candidate_support_20261106/measured.json'
        cases = []
        for case in read_json(fixture)['fixtures']:
            if case['name'] in ('recruit_positions', 'combat_slots'):
                host = LiteHost(case['spec'], args.rules)
                cases.append((case['name'], dict(host.decision(1), choice=0), host))
        assert len(cases) == 2
        model = runner.model
        start_weights = weights_sha256(model.state_dict())
        result = dict(architecture=ARCHITECTURE, initializer=initializer,
                      parameters=sum(p.numel() for p in model.parameters()),
                      rules_sha256=runner.manifest['rules']['rules_sha256'], teacher=runner.manifest['opponents'][0]['sha256'],
                      short_fixture_sha256=sha256(fixture), shard=str(args.shard), shard_sha256=sha256(args.shard),
                      torch_version=torch.__version__, timings=timings(runner, cases, long))
        assert weights_sha256(model.state_dict()) == start_weights
        if hasattr(model, 'board_readout'):
            # Exercise nonzero learned coefficients through save/reload and both runtimes.
            with torch.no_grad():
                model.board_readout.weight[:, 16:32] = torch.eye(16) * .125
                model.board_readout.weight[:, 32:] = torch.eye(16) * -.25
            runner.save()
            loaded, _ = load_model(runner.directory/'latest.pt', 'duel')
            assert torch.equal(loaded.board_readout.weight, model.board_readout.weight)
            result['parity'] = dict(max_error=verify_numerics(loaded, records), rows=len(records),
                                    turns=len({r['turn'] for r in records}))
        assert not runner.optimizer.state
        write_json(args.output, result)
        print(f'{args.output}: {result["parameters"]} parameters, {len(records)} raw rows')


if __name__ == '__main__':
    main()
