"""One fixed native teacher execution; no training, collection or strength claim."""
import argparse
import json
from pathlib import Path
import shutil
import time

from learning.common import ROOT, sha256, write_json
from learning.teachers import identity
import addons
import match


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    addon = output / 'teacher_ambush'
    shutil.copytree(ROOT / 'learning/teachers/gpt6astra', addon)
    for filename, content in zip(('_main.cfg', 'ai.cfg'), addons.configuration(addon.name)):
        (addon / filename).write_text(content, encoding='utf-8')
    write_json(addon / 'arena.json', dict(schema=2, id=addon.name, entry='lua/bot.lua'))
    for path in (addon / 'lua').glob('*.lua'):
        path.write_text(path.read_text().replace('~add-ons/gpt6astra/', '~add-ons/teacher_ambush/'))
    shutil.copyfile(ROOT / 'tests/fixtures/teacher_ambush.lua', addon / 'lua/bot.lua')
    package = output / 'teacher_ambush.zip'
    addons.pack(addon, package)
    terrain = [['Gg'] * 7 for _ in range(7)]
    terrain[2][1] = 'Gs^Ft'
    terrain[6][6] = terrain[0][6] = 'Kh'
    replay = output / 'ambush.json'
    result = match.play_game(bots=[str(package), 'baseline'], seed=713,
                            factions=['Drakes', 'Northerners'], max_turns=1,
                            wesnoth=args.wesnoth, replay_path=replay,
                            experiment_deadline=time.time() + 120,
                            fog=False, shroud=False,
                            map_override=dict(width=7, height=7, terrain=terrain,
                                              starts=[[7, 7], [7, 1]]))
    events = [json.loads(line) for line in replay.with_suffix('.events.jsonl').read_text().splitlines()]
    trace = {row['event']: row['data'] for row in events if row['event'].startswith('TEACHER_')}
    write_json(output / 'summary.json', dict(source=args.source, teacher=identity(),
        native_executable_sha256=sha256(args.wesnoth),
        entropy_sha256=sha256(ROOT / '.runtime/entropy.so'), result=result, trace=trace))
    print(json.dumps(dict(result=result, trace=trace), indent=2), flush=True)
    assert not result['faults'], result['faults']
    assert trace['TEACHER_BEFORE'] == dict(checked=True, ambusher_visible=False), trace
    assert trace['TEACHER_MOVE'] == dict(status=2005, ok=False, changed=True, x=3, y=4), trace
    assert trace['TEACHER_AFTER'] == dict(attacks=0, x=3, y=4, ambusher_visible=True), trace


if __name__ == '__main__':
    main()
