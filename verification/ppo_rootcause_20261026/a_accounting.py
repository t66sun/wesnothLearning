"""Read-only accounting of the completed v5_lite30h_20261025 run.

Prints, per format: batch/history composition, optimizer-step and decision
volume, KL-stop distribution, reward-controller version history, checkpoint
and selection identities, and validation panel coverage. It writes nothing.
"""
import collections
import json
import statistics
import sys

BASE = "/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025"
FORMATS = ("duel", "ffa4", "team2v2")


def stats(values):
    if not values:
        return "n=0"
    return "n=%d mean=%.3f median=%.3f min=%.3f max=%.3f sum=%.3f" % (
        len(values), statistics.mean(values), statistics.median(values),
        min(values), max(values), sum(values))


def main():
    for fmt in FORMATS:
        s = json.load(open("%s/%s/state.json" % (BASE, fmt), encoding="utf-8"))
        h = s["history"]
        bc = [e for e in h if e.get("method") == "bc"]
        ppo = [e for e in h if e.get("method") == "ppo"]
        other = [e for e in h if e.get("method") not in ("bc", "ppo")]
        print("=" * 78)
        print("FORMAT", fmt, "version", s.get("version"), "batch", s.get("batch"),
              "stage", s.get("stage"), "phase", s.get("phase"))
        print("history", len(h), "bc", len(bc), "ppo", len(ppo), "other", len(other))
        print("counters", json.dumps(s.get("counters"), sort_keys=True))
        for name, grp in (("bc", bc), ("ppo", ppo)):
            if not grp:
                continue
            print("  %s batches %d updates/batch %s" % (
                name, len(grp), stats([e.get("updates", 0) for e in grp])))
            print("  %s decisions/batch %s" % (
                name, stats([e.get("decisions_seen", 0) for e in grp])))
            print("  %s windows/batch %s" % (
                name, stats([e.get("sequence_windows", 0) for e in grp])))
            print("  %s families/batch %s" % (
                name, stats([e.get("unique_families_seen", 0) for e in grp])))
            print("  %s approx_kl %s" % (
                name, stats([e.get("approx_kl", 0.0) for e in grp])))
            print("  %s elapsed_h total %.3f mean %.4f" % (
                name, sum(e.get("elapsed_hours", 0) for e in grp),
                statistics.mean([e.get("elapsed_hours", 0) for e in grp])))
        exits = collections.Counter(e.get("exit") for e in ppo)
        print("  ppo exits", dict(exits))
        kl_zero = [e for e in ppo if e.get("kl_stopped") and e.get("updates", 0) == 0]
        kl_any = [e for e in ppo if e.get("kl_stopped")]
        print("  ppo kl_stopped %d (zero-update %d) of %d" % (
            len(kl_any), len(kl_zero), len(ppo)))
        # where in the run do KL stops sit
        if ppo:
            idx = [i for i, e in enumerate(ppo) if e.get("kl_stopped")]
            print("  kl_stop first/last ppo index", (idx[0], idx[-1]) if idx else None,
                  "fraction of post-BC run", "%.3f" % (len(kl_any) / max(1, len(ppo))))
        steps = [e.get("updates", 0) for e in ppo]
        for bucket in (0, 1, 2, 3, 4, 5, 8, 16, 32, 64):
            pass
        print("  ppo updates histogram", dict(sorted(collections.Counter(steps).items())[:12]))
        print("  planned/inspected/committed sample",
              [(e.get("planned_targets"), e.get("inspected_decisions"), e.get("committed_decisions"))
               for e in ppo[-3:]])
        print("  reward_controller", json.dumps(s.get("reward_controller"), sort_keys=True)[:900])
        rc = s.get("reward_controller") or {}
        print("  reward_version", rc.get("version"), "mode", rc.get("mode"))
        print("  best_key", s.get("best_key"), "bc_key", s.get("bc_key"),
              "ppo_key", s.get("ppo_key"), "best_kind", s.get("best_kind"))
        print("  champion", s.get("champion"))
        print("  bc_quality_best", json.dumps(s.get("bc_quality_best"))[:400])
        print("  bc_plateau", json.dumps(s.get("bc_plateau"))[:300])
        print("  status", json.dumps(s.get("status"))[:300])
        try:
            sel = json.load(open("%s/%s/selection.json" % (BASE, fmt), encoding="utf-8"))
            print("  selection.json", json.dumps(sel, sort_keys=True))
        except Exception as exc:
            print("  selection.json unreadable", repr(exc))
        try:
            gate = json.load(open("%s/%s/bc_gate.json" % (BASE, fmt), encoding="utf-8"))
            print("  bc_gate", json.dumps(gate, sort_keys=True)[:1200])
        except Exception as exc:
            print("  bc_gate unreadable", repr(exc))
        # validation cadence: which versions were measured as trend vs promotion
        import os
        vdir = "%s/%s/validation" % (BASE, fmt)
        val = []
        for name in sorted(os.listdir(vdir)):
            if not name.startswith("v"):
                continue
            try:
                d = json.load(open(os.path.join(vdir, name), encoding="utf-8"))
            except Exception:
                continue
            c = d.get("comparison", {}).get(fmt, {})
            val.append(dict(version=name[1:7], tier=d.get("tier"), blocks=c.get("blocks"),
                            planned=c.get("planned_blocks"), missing=c.get("missing_blocks"),
                            status=c.get("status"), diff=c.get("difference"),
                            policy=c.get("policy_score"), control=c.get("control_score")))
        print("  validation panels", len(val))
        for row in val[-6:]:
            print("   ", json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
