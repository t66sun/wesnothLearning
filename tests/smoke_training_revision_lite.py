"""Six finite lite games: real Astra teachers and BC/DAgger/PPO in all formats."""
from pathlib import Path
import argparse, json, os, time, gzip
import torch
from learning.common import ROOT, write_json
from learning.features import RULES_PATH, schema
from learning.formats import FORMATS, PLAYERS, TEAM2V2
from learning.model import Policy, ARCHITECTURE
from learning.export import export, verify_numerics, load_model
from learning.sample import collect
from learning.data import read_shards
from learning.sequences import read_raw_shards
from learning.train import train, checkpoint


def ident(fmt, label):
    from learning.data import split
    return next(f'lite-{label}-{fmt}-{i}' for i in range(1000) if split(f'lite-{label}-{fmt}-{i}') == 'train')


def map_board(name):
    return json.loads((ROOT / 'vendor/arena/maps' / name).read_text(encoding='utf-8'))


def factions_for(fmt):
    import params
    n = PLAYERS[fmt]
    return [params.FACTIONS[i % len(params.FACTIONS)] for i in range(n)]


def write_policy(model, destination):
    destination = Path(destination)
    addon = export({model.format_name: model}, destination, name='LitePolicy', mode='sample',
                   version='lite-smoke', package=False)
    torch.save(dict(model={k: v.detach().cpu() for k, v in model.state_dict().items()},
                    features=schema(), architecture=ARCHITECTURE, format=model.format_name),
               destination / 'model.pt')
    return addon


def make_job(out, fmt, label, policy_addon, teacher=False):
    n = PLAYERS[fmt]
    astra = str((ROOT / 'opponents/gpt6astra.zip').resolve())
    if teacher:
        bots = [astra] * n
        learning = dict(sides={'1': {'teacher': 'gpt6astra', 'version': 'teacher-frozen'}})
    else:
        bots = [str(Path(policy_addon).resolve()), astra]
        if n == 4: bots += [astra, astra]
        learning = dict(sides={'1': {'teacher': False, 'version': 'lite-smoke'}},
                        dagger_teacher=astra)
    game_id = ident(fmt, label)
    return dict(id=game_id, engine='lite', bots=bots, seed=103 if teacher else 211 + n * 31,
                factions=factions_for(fmt), teams=TEAM2V2 if fmt == 'team2v2' else None,
                map_override=map_board('arena2.json' if n == 2 else 'arena4.json'),
                max_turns=2, max_decisions=1000, deadline=time.time() + 300,
                rules_dir=str(RULES_PATH.parent.resolve()),
                allow_approximate=True, policy=None,
                output=str(out / 'replays' / (game_id + '.json')),
                shard=str(out / 'data' / (game_id + '.jsonl.gz')),
                format=fmt,
                meta=dict(format=fmt, phase='teacher' if teacher else 'ppo',
                          map='arena' + str(n), map_sha256='lite-smoke', map_partition='train',
                          context='astra_partner' if fmt == 'team2v2' else 'solo', engine_id='lite'),
                game_family=game_id, learning=learning)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args = p.parse_args()
    out = (ROOT / args.output).resolve(); assert out.is_relative_to(ROOT); out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1); torch.manual_seed(23)
    models = {f: Policy(f).to('cpu') for f in FORMATS}
    optimizers = {f: torch.optim.Adam(m.parameters(), lr=3e-4) for f, m in models.items()}

    teacher_jobs = [make_job(out, f, 'teacher', None, teacher=True) for f in FORMATS]
    teacher_results = collect(teacher_jobs, 3, out / 'teacher.jobs.jsonl')
    assert all(r['status'] == 'complete' and not r['result']['faults'] and r.get('training_eligible')
               for r in teacher_results), teacher_results
    bc = {}; audit_bc = {}; bc_updates = {}
    for job in teacher_jobs:
        fmt = job['format']
        bc[fmt] = read_shards([job['shard']], format_name=fmt)
        audit_bc[fmt] = read_raw_shards([job['shard']], format_name=fmt)
        assert bc[fmt], (fmt, 'empty teacher shard')
        assert all(r['source'] == 'astra' and r['teacher'] == 'gpt6astra' for r in bc[fmt])
        bc_updates[fmt] = train(models[fmt], optimizers[fmt], bc[fmt], 'bc', epochs=1, minibatch=8)
        assert bc_updates[fmt]['updates'] > 0

    policies = {f: write_policy(models[f], out / 'policies' / f) for f in FORMATS}
    policy_jobs = [make_job(out, f, 'policy', policies[f]) for f in FORMATS]
    policy_results = collect(policy_jobs, 3, out / 'policy.jobs.jsonl')
    assert all(r['status'] == 'complete' and not r['result']['faults'] and r.get('training_eligible')
               for r in policy_results), policy_results

    ppo_updates = {}; numerics = {}; bootstrap_rows = {}; dagger_queries = {}; engine_ids = set()
    audit_rehearsal = dict(audit_bc)
    for fmt in FORMATS:
        paths = [j['shard'] for j in policy_jobs if j['format'] == fmt]
        rows = read_shards(paths, format_name=fmt)
        assert rows, (fmt, 'empty policy shard')
        bootstrap_rows[fmt] = sum(r['truncated'] and r['bootstrap_value'] is not None for r in rows)
        assert all(r.get('value_valid', True) or r['bootstrap_value'] is not None for r in rows), \
            (fmt, 'policy row lacks terminal value and bootstrap', len(rows))
        engine_ids |= {r.get('engine_id') for r in rows}

        dagger_rows = []; audit_dagger_paths = []
        dagger_queries[fmt] = 0
        for path in paths:
            dagger = Path(path).with_name(Path(path).name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
            assert dagger.is_file(), (fmt, 'missing dagger shard')
            with gzip.open(dagger, 'rt', encoding='utf-8') as stream:
                raw = [json.loads(line) for line in stream]
            dagger_queries[fmt] += sum(bool(r.get('query_only')) for r in raw)
            if raw:
                dagger_rows.extend(read_shards([str(dagger)], format_name=fmt))
                audit_dagger_paths.append(str(dagger))
        assert dagger_queries[fmt] > 0, (fmt, 'no DAgger query labels')
        assert dagger_rows, (fmt, 'empty DAgger training rows')

        rehearsal = bc[fmt] + dagger_rows
        audit_rehearsal[fmt] = audit_bc[fmt] + read_raw_shards(audit_dagger_paths, format_name=fmt)
        ppo_updates[fmt] = train(models[fmt], optimizers[fmt], rows, 'ppo', epochs=1, minibatch=8,
                                 bc_records=rehearsal)
        assert ppo_updates[fmt]['updates'] > 0
        path = out / (fmt + '.pt')
        checkpoint(path, models[fmt], optimizers[fmt])
        restored, state = load_model(path, fmt, 'cpu')
        assert not state['cuda_rng']
        audit_rows = read_raw_shards(paths, format_name=fmt)
        numerics[fmt] = verify_numerics(restored, audit_rehearsal[fmt] + audit_rows)

    assert engine_ids == {'lite'}, engine_ids
    summary = dict(passed=True, engine='lite', workers=3, lite_games=len(teacher_jobs) + len(policy_jobs),
                   teacher_games=len(teacher_jobs), policy_games=len(policy_jobs),
                   teacher_formats=list(FORMATS),
                   bc_updates=bc_updates, ppo_updates=ppo_updates, bootstrap_rows=bootstrap_rows,
                   dagger_queries=dagger_queries, engine_ids=sorted(engine_ids),
                   python_lua_max_error=numerics,
                   rules_sha256=schema()['rules_sha256'])
    write_json(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
