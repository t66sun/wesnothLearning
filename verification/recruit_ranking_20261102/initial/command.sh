set -eu
root=/home/tongshu/acceptance/recruit_ranking_20261102
runtime=/home/tongshu/acceptance/recruit_label_full_20261102
mkdir "$root"
tar -xf "$root.tar" -C "$root"
cd "$runtime"
export PYTHONPATH="$runtime:$runtime/vendor/arena"
export OMP_NUM_THREADS=1
set +e
/usr/bin/time -p timeout --signal=TERM --kill-after=10 180 /home/tongshu/venv/bin/python -u "$root/tests/diagnose_recruit_ranking.py" --run /home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc --labels "$runtime/labels.json" --runtime-source d1c56453a55b251cbf4f6cb0aac6fe92238db0c8 --output "$root/ranking.json" > "$root/ranking.log" 2> "$root/ranking.err"
result=$?
printf '%s\n' "$result" > "$root/ranking.exit"
cat "$root/ranking.log" "$root/ranking.err"
exit "$result"
