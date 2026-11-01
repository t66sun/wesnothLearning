import json
import struct
import tempfile
import time
import unittest
from pathlib import Path

import torch
from lupa import LuaRuntime

from learning.export import export, lua_parameters
from learning.formats import FORMATS
from learning.model import Policy


class WeightExportTests(unittest.TestCase):
    def test_three_model_package_size_and_exact_loaded_weights(self):
        torch.manual_seed(19)
        models = {fmt: Policy(fmt) for fmt in FORMATS}
        # Include signed zero, subnormal and extreme finite float32 values.
        bits = [0, 0x80000000, 1, 0x80000001, 0x7f7fffff, 0xff7fffff]
        values = [struct.unpack('<f', struct.pack('<I', value))[0] for value in bits]
        for model in models.values():
            with torch.no_grad():
                model.unit_embedding.weight[0, :len(values)] = torch.tensor(values)

        def compare(expected, actual):
            if isinstance(expected, dict):
                self.assertEqual(set(expected), set(actual))
                for key, value in expected.items():
                    compare(value, actual[key])
            elif isinstance(expected, list):
                self.assertEqual(len(expected), len(actual))
                for i, value in enumerate(expected, 1):
                    compare(value, actual[i])
            elif isinstance(expected, float):
                self.assertEqual(struct.pack('<d', expected), struct.pack('<d', actual))
            else:
                self.assertEqual(expected, actual)

        with tempfile.TemporaryDirectory() as tmp:
            addon = export(models, tmp, package=False)
            sizes = {str(path.relative_to(addon)): path.stat().st_size
                     for path in addon.rglob('*') if path.is_file()}
            total = sum(sizes.values())
            print(json.dumps(dict(addon_bytes=total, weight_bytes={key: size for key, size in sizes.items()
                                                                 if key.startswith('lua/weights_')})))
            self.assertLessEqual(total, 16 * 1024 * 1024)
            for fmt, model in models.items():
                lua = LuaRuntime(unpack_returned_tuples=True)
                started = time.monotonic()
                weights = lua.execute((addon/'lua'/f'weights_{fmt}.lua').read_text(encoding='utf-8'))
                print(fmt, 'weight_load_seconds', time.monotonic() - started)
                compare(lua_parameters(model), weights)


if __name__ == '__main__':
    unittest.main()
