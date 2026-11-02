set -eu
cd /home/tongshu/acceptance
mkdir teacher_immunity_checked_20261103
cd teacher_immunity_checked_20261103
tar -xf /tmp/teacher_immunity_checked_20261103.tar
mkdir -p data/rules .extension .runtime
ln -s /home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered data/rules/1.18.8-combat-filtered
ln -s /home/tongshu/acceptance/retaliation_fixed_20261102/data/rules/1.18.8 data/rules/1.18.8
export PATH=/home/tongshu/.cargo/bin:/usr/local/bin:/usr/bin:/bin
export CARGO_TARGET_DIR=/home/tongshu/acceptance/teacher_immunity_20261103/engine_lite/target
export PYO3_PYTHON=/home/tongshu/venv/bin/python
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
PYTHONPATH=/home/tongshu/acceptance/filters_fixed_20261103/.extension:.:vendor/arena /home/tongshu/venv/bin/python -m unittest tests.v5.test_combat_immunity -v >baseline.log 2>&1 && exit 2
cargo test --manifest-path engine_lite/Cargo.toml >rust.log 2>&1
cargo build --release --manifest-path engine_lite/Cargo.toml >build.log 2>&1
cp /home/tongshu/acceptance/teacher_immunity_20261103/engine_lite/target/release/lib_engine_lite.so .extension/_engine_lite.so
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
/home/tongshu/venv/bin/python -m unittest tests.v5.test_combat_immunity tests.v5.test_combat_probability tests.v5.test_retaliation tests.v5.test_engine_contract tests.v5.test_rule_abilities_completion tests.v5.test_teacher_engine_identity tests.v5.test_astra_adaptation tests.v5.test_four_player_teacher tests.v5.test_differential_runner tests.v5.test_checkpoint_export_identity tests.v5.test_teacher_state_reuse -v >python.log 2>&1

/home/tongshu/venv/bin/python -m tests.diagnose_teacher_boards --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH_EXE" --source 90d796ae996354c954b14c0c6cdfe509f0acbae2 --output boards >boards.log 2>&1
/home/tongshu/venv/bin/python -m tests.diagnose_native_tactics --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH_EXE" --source 90d796ae996354c954b14c0c6cdfe509f0acbae2 --output immunity --case immune_poison --case immune_drain --case immune_plague --case immune_counter_poison --case immune_counter_drain --case immune_counter_plague >immunity.log 2>&1

