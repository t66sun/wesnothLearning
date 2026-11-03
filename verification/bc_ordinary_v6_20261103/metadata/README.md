# Ordinary BC run archive

The original Ubuntu run remains at `/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness`. Its enclosing directory contains the phase exit code (0), captured runtime identity and start/finish timestamps. The archive was assembled in a separate directory after the phase exited.

[run_metadata.tar.gz](run_metadata.tar.gz) contains all JSON and JSONL files in the run plus the original `runtime.json`, `phase.exit`, `phase.log`, `started.txt` and `finished.txt`. Its 138 regular files hold 4,386,273 original bytes and compress to 274,731 bytes. This includes the manifest, clock, scheduler events, controls, per-format states and counters, batch read/timing/optimizer history, jobs, gates, schedules, validation, report summaries and policy package metadata. [members.sha256](members.sha256) gives the relative path and original SHA256 of every member.

[artifacts.json](artifacts.json) lists every physical training shard in each format's `data/` tree and its two final checkpoint files. Each entry records the absolute path on Ubuntu, size in bytes and SHA256. Each shard also lists its final state references. Across the three formats, all 160 shards and six checkpoints total 350,432,181 bytes. The model payloads, training data, SQLite sequence caches and installed policy packages remain on Ubuntu.

| Format | Teacher shards | DAgger shards | Rollout shards | Bytes across shards | Latest + last BC checkpoint bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| duel | 56 | 4 | 4 | 71,550,480 | 18,917,079 |
| ffa4 | 48 | 0 | 0 | 90,521,554 | 18,880,599 |
| team2v2 | 48 | 0 | 0 | 132,404,882 | 18,157,587 |

Every shard referenced in a final `state.json` was present. Four additional duel files, `rollout-00036-duel-g0.jsonl.gz` through `g3.jsonl.gz`, exist on disk with no final state pool reference. Their four DAgger siblings are recorded under `dagger_shards`.

## Capture commands

The following commands run from this metadata directory. The Ubuntu staging directory was created fresh. `capture.py` reads the completed run, computes hashes sequentially and writes its outputs only in its own directory.

```sh
stage=/home/tongshu/acceptance/bc_v6_readiness_metadata_20261103
ssh -o BatchMode=yes cpuServer "mkdir '$stage'"
scp -q capture.py "cpuServer:$stage/capture.py"
ssh -o BatchMode=yes cpuServer "cd '$stage' && /home/tongshu/venv/bin/python -B capture.py && sha256sum -c SHA256SUMS"
scp -q "cpuServer:$stage/run_metadata.tar.gz" "cpuServer:$stage/members.sha256" \
    "cpuServer:$stage/artifacts.json" "cpuServer:$stage/SHA256SUMS" .
```

The four transferred or shared file digests were checked against [SHA256SUMS](SHA256SUMS). The archive SHA256 is `9a7abfd2d864257012015d32b879fae804f1168232c20248e4f378218d615d9c`. After transfer, every tar member name and byte digest was checked against `members.sha256`; the per-format pool memberships in the inventory were checked against the archived states.

```sh
sha256sum -c SHA256SUMS
audit=$(mktemp -d)
tar -xzf run_metadata.tar.gz -C "$audit"
(cd "$audit" && sha256sum -c -) < members.sha256
```
