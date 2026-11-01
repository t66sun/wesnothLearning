"""Compare prefix charges with shared history slots and their packed owners."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from learning.data import _shard_identity
from learning.sequences import _family_windows, _row_bytes, ITEM_BYTES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    saved = torch.load(args.run/'team2v2'/'last_bc.pt', map_location='cpu', weights_only=False)
    result = []
    for name in saved['runner']['teacher_shards']:
        path = Path(name)
        stat = path.stat()
        identity = _shard_identity(str(path), stat.st_size, stat.st_mtime_ns)
        if identity is None or identity[2] != 'train':
            continue
        windows, charged = _family_windows([(path, stat)], 'train', 'team2v2', 8)
        rows = [r for window in windows for r in window]
        slots = {id(slot):slot for row in rows for slot in row['_history']}
        owners = {}
        for slot in slots.values():
            owner = slot['global']
            if not isinstance(owner, np.ndarray):
                raise ValueError('this diagnostic expects the frozen packed corpus')
            while isinstance(owner.base, np.ndarray):
                owner = owner.base
            owners[id(owner)] = owner
        backing = sum(owner.nbytes for owner in owners.values())
        metadata = sum(ITEM_BYTES*(1+len(slot['spatial']['entities'])) for slot in slots.values())
        result.append(dict(path=str(path), family=identity[3], gz_bytes=stat.st_size,
            rows=len(rows), windows=len(windows), history_slots=len(slots),
            charged_prefix=charged, history_packed_bytes=backing,
            history_metadata_estimate=metadata, history_estimate=backing+metadata,
            target_estimate=sum(_row_bytes(row) for row in rows)))
    totals = {key:sum(row[key] for row in result) for key in result[0] if key not in ('path','family')}
    args.output.write_text(json.dumps(dict(totals=totals, families=result), indent=2)+'\n')
    print(json.dumps(totals), flush=True)


if __name__ == '__main__':
    main()
