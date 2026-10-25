"""V6: native and deterministic-lite Astra records keep separate identities."""
import copy
import unittest

from learning.adapters import ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION
from learning.data import validate_record
from learning.teachers import identity
from tests.v5 import helpers


class TeacherEngineIdentityTests(unittest.TestCase):
    def test_native_legacy_explicit_and_lite_profiles_are_accepted(self):
        lite=helpers.synthetic_decision_row()
        lite.update(identity())
        validate_record(lite)
        for engine_id in ('native','native-1.18.8'):
            native=copy.deepcopy(lite)
            native.update(engine='native',engine_id=engine_id,engine_version='1.18.8',
                rng_version='native-1.18.8',combat_version='native-1.18.8',native_version='1.18.8')
            native.pop('teacher_profile')
            native.pop('teacher_source_sha256')
            validate_record(native)
            native.update(teacher_profile='native',teacher_source_sha256='native-1.18.8')
            validate_record(native)
            native.update(data_pool='dagger',teacher_query=True)
            validate_record(native)

    def test_cross_engine_profiles_versions_and_sources_are_rejected(self):
        lite=helpers.synthetic_decision_row()
        lite.update(identity())
        native=dict(lite,engine_id='native',engine='native',engine_version='1.18.8',
                    rng_version='native-1.18.8',combat_version='native-1.18.8',
                    teacher_profile='native',teacher_source_sha256='native-1.18.8')
        cases=[dict(native,teacher_profile=COMBAT_VERSION),dict(lite,teacher_profile='native'),
               dict(native,rng_version=RNG_VERSION),dict(native,combat_version=COMBAT_VERSION),
               dict(lite,rng_version='native-1.18.8'),dict(lite,combat_version='native-1.18.8'),
               dict(native,teacher_source_sha256=identity()['teacher_source_sha256']),
               dict(lite,teacher_source_sha256='native-1.18.8'),dict(lite,engine='native'),
               dict(native,engine_id='unknown'),dict(native,engine_version=ENGINE_VERSION)]
        missing=dict(lite)
        missing.pop('teacher_profile')
        cases.append(missing)
        for changed in cases:
            with self.subTest(identity={k:changed.get(k) for k in ('engine_id','engine','rng_version','combat_version','teacher_profile','teacher_source_sha256')}):
                with self.assertRaisesRegex(ValueError,'teacher|identity'):
                    validate_record(changed)


if __name__ == '__main__':
    unittest.main()
