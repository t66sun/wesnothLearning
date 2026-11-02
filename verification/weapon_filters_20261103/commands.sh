set -eu
cd /home/tongshu/acceptance
mkdir filters_verified_20261103
cd filters_verified_20261103
tar -xf ../filters-verified.tar
mkdir -p data/rules .extension .runtime
ln -s /home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered data/rules/1.18.8-combat-filtered
ln -s /home/tongshu/acceptance/retaliation_fixed_20261102/data/rules/1.18.8 data/rules/1.18.8
export PATH=/home/tongshu/.cargo/bin:/usr/local/bin:/usr/bin:/bin
export PYO3_PYTHON=/home/tongshu/venv/bin/python
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
cargo test --manifest-path engine_lite/Cargo.toml >rust.log 2>&1
cargo build --release --manifest-path engine_lite/Cargo.toml >build.log 2>&1
cp engine_lite/target/release/lib_engine_lite.so .extension/_engine_lite.so
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
/home/tongshu/venv/bin/python -m unittest tests.v5.test_weapon_filters tests.v5.test_weapon_accuracy tests.v5.test_weapon_declarations tests.v5.test_amla tests.v5.test_amla_declarations tests.v5.test_coverage_audit_regressions tests.v5.test_rules_catalog tests.test_bundle tests.test_bundle_scripts tests.v5.test_combat_probability tests.v5.test_retaliation tests.v5.test_engine_contract tests.v5.test_rule_abilities_completion tests.v5.test_teacher_engine_identity tests.v5.test_astra_adaptation tests.v5.test_four_player_teacher tests.v5.test_differential_runner tests.v5.test_checkpoint_export_identity tests.test_core -v >python.log 2>&1
/home/tongshu/venv/bin/python tests/diagnose_native_weapon_filters.py --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH_EXE" --source 4feb937 --output native-weights >native-weights.log 2>&1
/home/tongshu/venv/bin/python tests/diagnose_native_tactics.py --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH_EXE" --source 4feb937 --output native-tactics >native-tactics.log 2>&1
