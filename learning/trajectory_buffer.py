"""Replayable per-game records with bounded live decision memory."""
import pickle
import struct
import tempfile
import zlib

from .rowpack import compact_row


def _metric_view(row):
    view = {key: row[key] for key in ('side', 'turn', 'decision', 'global', 'global_features',
            'reward_raw', 'reward_after', 'source', 'teacher', 'format', 'rules_version', 'metric_event') if key in row}
    if 'spatial' in row:
        view['spatial'] = {'entities': row['spatial']['entities']}
    if row.get('memory_write'):
        view['memory_write'] = _metric_view(row['memory_write'])
    return view


class TrajectoryBuffer:
    """Spool exact records; a read materializes only one decision at a time.

    These are private temporary records, not a persisted dataset format. The
    existing shard writer still owns labels, rewards and the disk contract.
    """
    def __init__(self):
        self.file = tempfile.TemporaryFile(mode='w+b')
        self.count = self.truncated = 0
        self.coverage = dict(total=0, matched=0, kinds={kind: dict(total=0, matched=0)
                            for kind in ('recruit', 'move', 'attack', 'move_attack', 'end_turn')})

    def append(self, row):
        compact = compact_row(row)
        payload = zlib.compress(pickle.dumps(compact, protocol=5), level=1)
        self.file.seek(0, 2)
        self.file.write(struct.pack('<I', len(payload)))
        self.file.write(payload)
        self.count += 1
        self.truncated += bool(row.get('timing', {}).get('truncated', False))
        matched = row.get('choice', -1) >= 0
        self.coverage['total'] += 1
        self.coverage['matched'] += matched
        kind = row['actual']['kind']
        names = ('move_attack', 'attack') if kind == 'move_attack' else (kind,)
        for name in names:
            self.coverage['kinds'][name]['total'] += 1
            self.coverage['kinds'][name]['matched'] += matched

    def __len__(self):
        return self.count

    def __iter__(self):
        offset = 0
        for _ in range(self.count):
            self.file.seek(offset)
            size = struct.unpack('<I', self.file.read(4))[0]
            payload = self.file.read(size)
            offset = self.file.tell()
            yield pickle.loads(zlib.decompress(payload))

    def metric_rows(self):
        for row in self:
            yield _metric_view(row)

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
