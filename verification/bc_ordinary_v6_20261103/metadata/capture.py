"""Package the completed BC run's metadata and fingerprint its retained training inputs."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import tarfile


SOURCE = Path('/home/tongshu/acceptance/bc_v6_readiness_20261103')
RUN = SOURCE / 'runs/bc_readiness'
OUT = Path(__file__).resolve().parent


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if (SOURCE / 'phase.exit').read_text().strip() != '0':
    raise ValueError('expected the completed phase')
metadata = [SOURCE / name for name in ('phase.exit', 'phase.log', 'started.txt', 'finished.txt', 'runtime.json')]
metadata += [p for p in RUN.rglob('*') if p.is_file() and p.suffix in ('.json', '.jsonl')]
metadata.sort(key=lambda p: p.relative_to(SOURCE).as_posix())
member_hashes = OUT / 'members.sha256'
with member_hashes.open('x') as listing:
    for path in metadata:
        listing.write(f'{digest(path)}  {path.relative_to(SOURCE).as_posix()}\n')
archive = OUT / 'run_metadata.tar.gz'
with archive.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as packed:
    with tarfile.open(fileobj=packed, mode='w|') as tar:
        for path in metadata:
            tar.add(path, arcname=path.relative_to(SOURCE).as_posix(), recursive=False)

inventory = dict(source=str(SOURCE), run=str(RUN), formats={})
for fmt in ('duel', 'ffa4', 'team2v2'):
    directory = RUN / fmt
    state = json.loads((directory / 'state.json').read_bytes())
    pools = {key: set(map(Path, state[key])) for key in ('teacher_shards', 'dagger_shards', 'policy_shards')}
    shards = sorted((directory / 'data').rglob('*.jsonl.gz'))
    missing = set.union(*pools.values()) - set(shards)
    if missing:
        raise ValueError(f'{fmt} final state references missing shards: {missing}')
    counts = Counter()
    files = []
    for path in shards + [directory / 'latest.pt', directory / 'last_bc.pt']:
        if path.suffix == '.pt':
            role = path.stem
        elif path.name.endswith('.dagger.jsonl.gz'):
            role = 'dagger'
        else:
            role = path.name.split('-', 1)[0]
        item = dict(path=str(path), role=role, bytes=path.stat().st_size, sha256=digest(path))
        if path.suffix != '.pt':
            item['final_state_pools'] = [key for key, paths in pools.items() if path in paths]
        files.append(item)
        counts[role] += 1
    inventory['formats'][fmt] = dict(file_counts=dict(sorted(counts.items())),
        state_pool_counts={key: len(paths) for key, paths in pools.items()},
        shard_bytes=sum(f['bytes'] for f in files if 'final_state_pools' in f),
        checkpoint_bytes=sum(f['bytes'] for f in files if 'final_state_pools' not in f),
        files=files)
with (OUT / 'artifacts.json').open('x') as stream:
    json.dump(inventory, stream, indent=2)
    stream.write('\n')
with (OUT / 'SHA256SUMS').open('x') as sums:
    for path in (archive, member_hashes, OUT / 'artifacts.json', Path(__file__).resolve()):
        sums.write(f'{digest(path)}  {path.name}\n')
