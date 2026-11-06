"""Small native entry smoke, not playing-strength evidence."""
import argparse
import json
from pathlib import Path
from learning.common import ROOT
import match


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--turns', type=int, default=2)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = (ROOT / 'SOURCE_COMMIT').read_text().strip()
    manifest = dict(source_commit=source, turns=args.turns, scope='native-entry-only')
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    teacher = str(ROOT / 'learning/teachers/search_teacher')
    baseline = str(ROOT / 'learning/teachers/gpt6astra')
    for fmt, bots, teams in (
        ('duel', [teacher, baseline], None),
        ('ffa4', [teacher, baseline, 'baseline', 'baseline'], None),
        ('team2v2', [teacher, baseline, teacher, baseline], [1, 2, 1, 2]),
    ):
        result = match.play_game(bots, seed=711, teams=teams, max_turns=args.turns,
                                 timeout=2, first_timeout=20,
                                 wesnoth=str(ROOT / '.runtime/install/bin/wesnoth'),
                                 replay_path=str(args.output / (fmt + '.json')))
        print(json.dumps(dict(format=fmt, result=result)), flush=True)
        assert not result['faults'], result['faults']
        assert result['actions'] > 0


if __name__ == '__main__':
    main()
