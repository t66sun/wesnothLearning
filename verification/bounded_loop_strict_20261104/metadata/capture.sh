set -eu
root=$1
out=$2
mkdir "$out"
cd "$root"
{
    printf '%s\n' preparation.started started.txt finished.txt driver.exit driver.log inputs.sha256 runtime.json
    find verification/bounded_loop_observed runs/bounded_loop -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.log' \) -print
    if test -f delivery/bounded_loop/export.json; then printf '%s\n' delivery/bounded_loop/export.json; fi
} | LC_ALL=C sort -u > "$out/members.txt"
tar -czf "$out/run_metadata.tar.gz" --files-from="$out/members.txt"
{
    find verification/bounded_loop_observed/checkpoints -type f -name '*.pt' -print
    for fmt in duel ffa4 team2v2; do
        find "runs/bounded_loop/$fmt" -maxdepth 1 -type f -name '*.pt' -print
        find "runs/bounded_loop/$fmt/data" -type f -name '*.jsonl.gz' -print
    done
    if test -d delivery/bounded_loop; then find delivery/bounded_loop -type f -name '*.zip' -print; fi
} | LC_ALL=C sort | xargs -r -d '\n' sha256sum > "$out/artifacts.sha256"
cd "$out"
sha256sum run_metadata.tar.gz members.txt artifacts.sha256 > SHA256SUMS
cat SHA256SUMS