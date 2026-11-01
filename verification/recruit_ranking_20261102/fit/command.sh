set -eu
root=/home/tongshu/acceptance/recruit_retention_fit_20261102
runtime=/home/tongshu/acceptance/recruit_label_full_20261102
mkdir "$root"
tar -xf /home/tongshu/acceptance/recruit_retention_probe_20261102.tar -C "$root"
cd "$runtime"
export PYTHONPATH="$runtime:$runtime/vendor/arena"
export OMP_NUM_THREADS=1
sha256sum learning/model.py learning/bc.py learning/updates.py learning/train.py learning/data.py > "$root/runtime.sha256"
set +e
/usr/bin/time -p timeout --signal=TERM --kill-after=10 1080 /home/tongshu/venv/bin/python -u "$root/tests/diagnose_bc_recruit_retention.py" --run /home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc --format team2v2 --updates 600 --seconds 900 --output "$root/curve.json" --selection-output "$root/selection.json" > "$root/curve.log" 2> "$root/curve.err"
result=$?
printf '%s\n' "$result" > "$root/curve.exit"
tail -4 "$root/curve.log"
cat "$root/curve.err"
exit "$result"
