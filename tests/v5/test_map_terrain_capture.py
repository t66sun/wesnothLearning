"""Map combinations enter the native exporter inventory without alias guessing."""
import json
from pathlib import Path
import tempfile
import unittest

from engine_lite.capture import map_terrain_codes


class MapTerrainCaptureTests(unittest.TestCase):
    def test_frozen_and_arena_maps_preserve_all_compound_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'native.json').write_text(json.dumps(dict(board=dict(
                terrain=[['Gg^Efm', 'Hh^Vhh'], ['Gg', 'Gs^Fp']]))), encoding='utf-8')
            (root / 'arena.json').write_text(json.dumps(dict(
                terrain=[['Gg', 'Tb^Tf']])), encoding='utf-8')
            self.assertEqual(map_terrain_codes(root),
                             {'Gg', 'Gg^Efm', 'Hh^Vhh', 'Gs^Fp', 'Tb^Tf'})

    def test_malformed_terrain_is_rejected_instead_of_omitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'bad.json').write_text(json.dumps(dict(
                board=dict(terrain=['Gg,Hh^Vhh']))), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'native terrain codes'):
                map_terrain_codes(root)
