import json
import unittest

import numpy as np

from learning.rowpack import float_count, pack_line, plain_row, row_meta, unpack_line


def sample_row():
    return {
        'schema': 4,
        'game_id': 'g1',
        'split': 'train',
        'turn': 12,
        'side': 2,
        'choice': 3,
        'kind': 'attack',
        'truncated': False,
        'global': [1 / 3] * 45,
        'opponents': [[2 / 7] * 19, [5 / 9] * 19],
        'spatial': {'board': [[float(x + y) for x in range(16)] for y in range(9)],
                    'entities': [{'id': 7 + i, 'leader': i % 2, 'side': i % 4, 'turn': 12,
                                  'type_index': 5, 'x': i, 'y': i + 1,
                                  'features': [1 / 7 * i] * 94} for i in range(8)]},
        'candidates': [{'features': [2 / 3] * 111, 'geometry': [3 / 11] * 16, 'local': [7 / 13] * 171,
                        'kind': 'move', 'rule': 'move'} for _ in range(16)],
    }


class RowpackTest(unittest.TestCase):

    def test_integer_elements_inside_vectors_are_packed_not_boxed(self):
        # Recorders emit ``0`` for integral features next to fractional ones; a
        # single int must not stop the whole vector from becoming one array.
        row = sample_row()
        row['candidates'][0]['local'] = [0, 1, 0.5, 2] + [0.25] * 167
        line = pack_line(row)
        assert line.startswith('{"v":2,"m":'), line[:32]
        back, _ = unpack_line(line)
        local = back['candidates'][0]['local']
        assert isinstance(local, np.ndarray), type(local)
        assert np.allclose(local, row['candidates'][0]['local'])
        # Scalars keep their JSON type so label consumers still see ints.
        assert isinstance(back['turn'], int) and not isinstance(back['turn'], bool)

    def test_packed_round_trip_preserves_labels_and_floats(self):
        row = sample_row()
        line = pack_line(row)
        assert line.startswith('{"v":2,"m":'), line[:32]
        back, numeric_bytes = unpack_line(line)
        assert numeric_bytes > 0
        for name in ('schema', 'turn', 'side', 'choice', 'kind', 'truncated', 'game_id', 'split'):
            assert back[name] == row[name], name
            assert type(back[name]) is type(row[name]), name
        entity = back['spatial']['entities'][0]
        assert type(entity['type_index']) is int and entity['type_index'] == 5
        assert type(entity['x']) is int and entity['x'] == 0
        assert np.allclose(back['global'], row['global'])
        assert np.shape(back['spatial']['board']) == (9, 16)
        assert np.allclose(back['spatial']['board'], row['spatial']['board'])
        assert np.allclose(back['candidates'][3]['local'], row['candidates'][3]['local'])
        assert float_count(back) == float_count(row)

    def test_plain_rows_stay_json_and_readable(self):
        row = {'turn': 3, 'split': 'train', 'global': [0.5] * 4, 'candidates': []}
        line = pack_line(row)
        assert line == json.dumps(row, separators=(',', ':'))
        back, numeric_bytes = unpack_line(line)
        assert back == row and numeric_bytes == 0
        assert row_meta(line) == row

    def test_metadata_reads_identity_without_decoding_numbers(self):
        row = sample_row()
        meta = row_meta(pack_line(row))
        assert meta['turn'] == 12 and meta['split'] == 'train' and meta['game_id'] == 'g1'
        assert isinstance(meta['global'], dict) and meta['global']['$'][1] == 45

    def test_plain_row_restores_json_shapes(self):
        back, _ = unpack_line(pack_line(sample_row()))
        plain = plain_row(back)
        again, _ = unpack_line(pack_line(plain))
        assert isinstance(plain['spatial']['board'], list)
        assert plain_row(again)['candidates'][0]['features'] == plain['candidates'][0]['features']


if __name__ == '__main__':
    unittest.main()
