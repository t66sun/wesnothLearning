"""Read candidate wall timings already stored in six frozen PPO batches."""
import argparse
import gzip
import json
from pathlib import Path

from learning.rowpack import row_meta
from census import sha256, summary


def inspect(root):
    result = []
    for fmt in ('duel', 'team2v2'):
        state = json.loads((root / fmt / 'state.json').read_text())
        history = [h for h in state['history'] if h['method'] == 'ppo']
        for entry in (history[0], history[len(history) // 2], history[-1]):
            path = root / fmt / 'schedules' / f"ppo-batch-{entry['batch']:06}.json"
            jobs = json.loads(path.read_text())
            candidates = []
            raw = queries = labels = 0
            identities = {}
            for job in jobs:
                policy = Path(job['shard'])
                dagger = policy.with_name(policy.name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
                for shard in (policy, dagger):
                    identities[str(shard)] = sha256(shard)
                    with gzip.open(shard, 'rt') as stream:
                        for line in stream:
                            row = row_meta(line)
                            if shard == policy:
                                candidates.append(row['timing']['ms'])
                            else:
                                raw += 1
                                queries += bool(row.get('query_only'))
                                labels += row['choice'] >= 0
            assert len(candidates) == entry['eligible_decisions']
            result.append(dict(format=fmt, batch=entry['batch'],
                recorded_learner_candidate_ms=summary(candidates),
                dagger_raw_rows=raw, dagger_queries=queries, dagger_labels=labels,
                inputs=identities))
    return dict(note='Historical C.generate wall milliseconds for recorded learner decisions only. '
                     'Excludes observation capture, teacher planning, execution, opponent decisions and process CPU.',
                batches=result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(inspect(args.run), indent=2) + '\n')
