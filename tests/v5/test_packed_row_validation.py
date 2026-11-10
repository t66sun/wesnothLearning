"""Packed numeric validation keeps the public row checks."""
import copy
import unittest
from unittest.mock import patch

import numpy as np

from learning.data import validate_record
from learning.rowpack import pack_line, unpack_line
from tests.v5.helpers import synthetic_decision_row


class PackedRowValidationTests(unittest.TestCase):
    def setUp(self):
        self.plain = synthetic_decision_row()
        with patch('learning.rowpack.PACK_MIN_FLOATS', 0):
            self.packed, _ = unpack_line(pack_line(self.plain))
        self.assertIsInstance(self.packed['spatial']['board'], np.ndarray)

    def test_checks_packed_board_as_one_array(self):
        with patch('numpy.isfinite', wraps=np.isfinite) as finite:
            validate_record(self.packed)
        self.assertTrue(any(call.args[0] is self.packed['spatial']['board']
                            for call in finite.call_args_list))

    def test_packed_and_legacy_rows_reject_bad_numeric_values(self):
        for row in (self.plain, self.packed):
            for field, error in (('board', 'invalid public spatial grid'),
                                 ('local', 'nonfinite action context')):
                with self.subTest(packed=row is self.packed, field=field):
                    bad = copy.deepcopy(row)
                    if field == 'board':
                        bad['spatial']['board'][0][0][0] = float('nan')
                    else:
                        bad['candidates'][0]['local'][0] = float('inf')
                    with self.assertRaisesRegex(ValueError, error):
                        validate_record(bad)
