set -eu
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1
PYTHON=/home/tongshu/venv/bin/python
WESNOTH=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
cd /home/tongshu/acceptance/teacher_boards_final_20261103
"$PYTHON" -m tests.diagnose_teacher_boards --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH" --source 0111083915a5a5076f39e43be7c67c9e4739b447 --output boards
# First invocation completed poison/drain, then failed the nonlethal plague fixture.
"$PYTHON" -m tests.diagnose_native_tactics --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH" --source 0111083915a5a5076f39e43be7c67c9e4739b447 --output immunity --case immune_poison --case immune_drain --case immune_plague --case immune_counter_poison --case immune_counter_drain --case immune_counter_plague
# Separate invocation after the failed command, in the final fresh source directory:
cd /home/tongshu/acceptance/immunity_native_final_20261103
"$PYTHON" -m tests.diagnose_native_tactics --rules data/rules/1.18.8-combat-filtered --wesnoth "$WESNOTH" --source afec90f76d7157315a25974ba758cee315e1be8a --output immunity --case immune_plague --case immune_counter_poison --case immune_counter_drain --case immune_counter_plague
