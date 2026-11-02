"""The derived control changes only the already-accepted ambush execution hunk."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from lupa import LuaError

from tests.teacher_control_compatibility import apply_ambush_compatibility
from tests.v5.test_teacher_movement import ROOT, STRATEGIES, scene


class TeacherControlCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with ZipFile(ROOT / 'data/opponents/gpt6astra.zip') as frozen:
            frozen.extractall(temporary.name)
        self.staged = Path(temporary.name) / 'gpt6astra'

    def test_ambush_halts_the_original_frozen_control_plan(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy, phase='original'):
                source = (self.staged / f'lua/{strategy}.lua').read_text()
                lua, teacher = scene(strategy, 2005, source=source)
                with self.assertRaises(LuaError):
                    teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
        apply_ambush_compatibility(self.staged)
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy, phase='derived'):
                source = (self.staged / f'lua/{strategy}.lua').read_text()
                lua, teacher = scene(strategy, 2005, source=source)
                teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
                self.assertEqual(lua.globals().calls.move, 1)
                self.assertEqual(lua.globals().calls.attack, 0)
                self.assertEqual((lua.globals().actor.x, lua.globals().actor.y), (3, 4))

    def test_normal_arrival_and_other_move_errors_keep_their_behavior(self):
        apply_ambush_compatibility(self.staged)
        for strategy in STRATEGIES:
            source = (self.staged / f'lua/{strategy}.lua').read_text()
            with self.subTest(strategy=strategy, status=0):
                lua, teacher = scene(strategy, 0, source=source)
                teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
                self.assertEqual(lua.globals().calls.attack, 1)
            with self.subTest(strategy=strategy, status=2008):
                lua, teacher = scene(strategy, 2008, source=source)
                with self.assertRaises(LuaError):
                    teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
                self.assertEqual(lua.globals().calls.attack, 0)

    def test_reversing_the_known_hunks_restores_every_parent_byte(self):
        original = {p.relative_to(self.staged).as_posix(): p.read_bytes()
                    for p in self.staged.rglob('*') if p.is_file()}
        metadata = apply_ambush_compatibility(self.staged)
        changed = {f'lua/{strategy}.lua' for strategy in STRATEGIES}
        self.assertEqual(set(metadata['files']), changed)
        old = b'        assert((full and final_step and ai.move_full or ai.move)(u,next_hex).ok)'
        for relative, before in original.items():
            with self.subTest(file=relative):
                after = (self.staged / relative).read_bytes()
                if relative not in changed:
                    self.assertEqual(after, before)
                    continue
                newline = b'\r\n' if b'\r\n' in before else b'\n'
                new = newline.join((
                    b'        local result=(full and final_step and ai.move_full or ai.move)(u,next_hex)',
                    b'        if result.status==2005 then return false end -- Native ambush interrupts a legal move.',
                    b'        assert(result.ok)',
                ))
                self.assertEqual(after.count(new), 1)
                self.assertEqual(after.replace(new, old), before)
                self.assertEqual(metadata['files'][relative], dict(
                    old_sha256=sha256(before).hexdigest(), new_sha256=sha256(after).hexdigest()))
                derived = after.decode().replace('\r\n', '\n')
                maintained = (ROOT / 'learning/teachers/gpt6astra' / relative).read_text()
                # The same helper already has real native ambush acceptance.
                start, end = 'local function move(', '\nfunction M:execution('
                self.assertEqual(derived.split(start)[1].split(end)[0],
                                 maintained.split(start)[1].split(end)[0])


if __name__ == '__main__':
    unittest.main()
