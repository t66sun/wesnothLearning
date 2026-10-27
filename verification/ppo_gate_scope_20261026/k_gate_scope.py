"""Count the BC corpus' distinct scenarios per format (read-only).

The BC gate artifact reports game counts and per-kind decision counts but never
how many distinct scenarios those games span, so the gate cannot be audited for
independence. This probe measures the corpus side of that question: how many
distinct (map, factions, teams) scenarios and distinct families the teacher
shards contain, and how the per-game family/split assignment distributes.

Run:
  WL_RUN=<run dir> python k_gate_scope.py [--format duel] [--maxfiles 0]
"""
import argparse
import glob
import gzip
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.environ.get("WL_SOURCE", "."))
from learning.rowpack import unpack_line  # noqa: E402


def scenario_key(row):
    m = row
    return (
        m.get("format"),
        m.get("map_sha256") or m.get("map"),
        json.dumps(m.get("factions")),
        json.dumps(m.get("teams")),
    )


def scan(path, games, families, scenarios, splits):
    seen_game = set()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except ValueError:
                continue
            row, _ = unpack_line(line) if "v" in payload else (payload, b"")
            gid = row.get("game_id")
            if gid in seen_game:
                continue
            seen_game.add(gid)
            games.add(gid)
            fam = row.get("game_family")
            families[fam] += 1
            scenarios[scenario_key(row)] += 1
            splits[row.get("split")] += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", default="duel")
    parser.add_argument("--maxfiles", type=int, default=0, help="0 = all")
    args = parser.parse_args()
    run = os.environ["WL_RUN"]
    data = os.path.join(run, args.format, "data")
    paths = sorted(glob.glob(os.path.join(data, "teacher-*%s*" % args.format)))
    if args.maxfiles:
        paths = paths[: args.maxfiles]
    games, families, scenarios, splits = set(), Counter(), Counter(), Counter()
    for path in paths:
        scan(path, games, families, scenarios, splits)
    print("format", args.format, "shards", len(paths), "games", len(games))
    print("distinct families", len(families))
    print("distinct scenarios", len(scenarios))
    print("split counts (per game)", dict(splits))
    print("games per scenario",
          sorted(Counter(scenarios.values()).items()))
    top = scenarios.most_common(6)
    print("top scenarios")
    for key, count in top:
        print("  %3d  %s" % (count, key))


if __name__ == "__main__":
    main()
