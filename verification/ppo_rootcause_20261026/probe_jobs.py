import json, sys, collections

BASE = "/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025"
fmt = sys.argv[1] if len(sys.argv) > 1 else "duel"

# jobs.jsonl: first record of each phase/meta
seen = {}
kind = collections.Counter()
meta_keys = collections.Counter()
with open(BASE + "/" + fmt + "/jobs.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        try:
            r = json.loads(line)
        except Exception:
            continue
        kind[r.get("status", "nokey")] += 1
        m = r.get("meta", {})
        phase = m.get("phase", "?")
        meta_keys[phase] += 1
        if phase not in seen:
            seen[phase] = r
print("status counts", dict(kind))
print("phases", dict(meta_keys))
for phase, r in seen.items():
    print("=== phase", phase)
    print(" top keys", list(r.keys()))
    print(" meta", json.dumps(r.get("meta"))[:1200])
    if "result" in r:
        print(" result keys", list(r["result"].keys()))
        print(" result", json.dumps(r["result"])[:800])
