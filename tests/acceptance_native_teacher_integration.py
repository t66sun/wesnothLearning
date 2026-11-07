"""Fixed Native query/collector fixtures, not corpus or strength acceptance."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import time

from learning.common import ROOT, write_json
import addons
import match
import native
from learning.features import schema
from learning.sample import play_job
from learning.sequences import read_raw_shards
from learning.teachers.registry import freeze_set
from learning.teachers.runtime import prepare_job


def support(directory):
    target = directory/'LearningSupport/lua'
    target.mkdir(parents=True)
    for source in (ROOT/'lua').glob('*.lua'):
        (target/source.name).write_text(source.read_text().replace('@ADDON@', 'LearningSupport'))
    (target/'features.lua').write_text('return '+native.lua(schema()))
    return str(target.parent)


def audit_bot(directory, queries, hidden, hang=False):
    target = directory/'TeacherQueryAudit'
    (target/'lua').mkdir(parents=True)
    for name, content in zip(('_main.cfg', 'ai.cfg'), addons.configuration(target.name)):
        (target/name).write_text(content)
    write_json(target/'arena.json', dict(schema=2, id=target.name, entry='lua/bot.lua'))
    shutil.copyfile(ROOT/'tests/fixtures/integrated_teacher_audit.lua', target/'lua/bot.lua')
    (target/'lua/options.lua').write_text('return '+native.lua(dict(queries=queries, hidden=hidden, hang=hang)))
    return str(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    contract = freeze_set(args.output/'teachers', 'mixed-20261107')
    shared = support(args.output)
    write_json(args.output/'manifest.json', dict(source_commit=(ROOT/'SOURCE_COMMIT').read_text().strip(),
               teachers=contract, scope='fixed Native fixtures; no optimizer or strength claim'))
    traces, results = {}, {}
    terrain = [['Gg']*15 for _ in range(15)]
    starts = [[2, 2], [14, 14], [2, 14], [14, 2]]
    for x, y in starts:
        terrain[y-1][x-1] = 'Kh'
        terrain[y-1][x-2] = 'Ch'
    for fmt, roles in contract['formats'].items():
        players = 2 if fmt == 'duel' else 4
        teams = [1, 2, 1, 2] if fmt == 'team2v2' else None
        spec = roles['supervision']
        for case, queries, hidden in (('control', 0, False), ('query', 2, False), ('hidden', 2, True)):
            name = fmt+'-'+case
            folder = args.output/name
            bot = audit_bot(folder, queries, hidden)
            job = prepare_job(dict(format=fmt, bots=[bot]+['baseline']*(players-1), teacher_roles=roles,
                         learning=dict(support=shared, dagger_teacher=spec['package'], sides={'1': {'teacher': False}})), 'native')
            result = match.play_game(job['bots'], seed=713, teams=teams,
                        factions=['Loyalists', 'Northerners', 'Rebels', 'Drakes'][:players],
                        max_turns=1, wesnoth=str(ROOT/'.runtime/install/bin/wesnoth'),
                        replay_path=folder/'audit.json', experiment_deadline=time.time()+120,
                        learning=job['learning'], fog=True, shroud=True, share_view=False, share_maps=False,
                        map_override=dict(width=15, height=15, terrain=terrain, starts=starts[:players]))
            with gzip.open(folder/'audit.events.jsonl.gz', 'rt') as stream:
                events = [json.loads(line) for line in stream]
            rows = [r['data'] for r in events if r['event'] == 'INTEGRATED_QUERY_AUDIT']
            assert not result['faults'], result
            assert len(rows) == 1, (name, rows)
            results[name], traces[name] = result, rows[0]
            print(json.dumps(dict(case=name, faults=result['faults'], seconds=result['seconds'])), flush=True)
        control, query, hidden = (traces[fmt+'-'+case] for case in ('control', 'query', 'hidden'))
        for key in ('public', 'draws', 'successor_id', 'successor_underlying'):
            assert control[key] == query[key], (fmt, key)
        for key in ('public', 'plan'):
            assert query[key] == hidden[key], (fmt, 'hidden', key)
        assert query['queries'][0]['query_budget'] == spec['first_timeout']
        assert query['queries'][1]['query_budget'] == spec['timeout']
        # One ordinary round exercises the real macro collector and row writer.
        name = fmt+'-collector'
        result = play_job(dict(id=name, format=fmt, engine='native', teacher_roles=roles,
                    bots=[spec['package']]+['baseline']*(players-1), seed=719, teams=teams,
                    factions=['Loyalists', 'Northerners', 'Rebels', 'Drakes'][:players],
                    max_turns=1, deadline=time.time()+120, wesnoth=str(ROOT/'.runtime/install/bin/wesnoth'),
                    output=str(args.output/name/'game.json'), shard=str(args.output/name/'rows.jsonl.gz'),
                    learning=dict(support=shared,sides={'1': {'teacher': spec['teacher'], 'version': 'fixture'}})))
        results[name] = result
        assert result['status'] == 'complete' and not result['result']['faults'], result
        rows = read_raw_shards([args.output/name/'rows.jsonl.gz'], format_name=fmt)
        assert rows and any(row['choice'] >= 0 for row in rows), result
        assert all(row['teacher_package_sha256'] == spec['package_sha256'] and row['source'] == 'teacher'
                   and row['teacher_impl'] == spec['teacher'] for row in rows)
        assert any(row['actual']['kind'] == 'recruit' for row in rows)
        print(json.dumps(dict(case=name, rows=len(rows), coverage=result['coverage'])), flush=True)
    # An actual hanging query must terminate the game, never produce a draw/label.
    folder = args.output/'watchdog'
    bot = audit_bot(folder, 0, False, hang=True)
    result = match.play_game([bot, 'baseline'], seed=713, max_turns=1,
                wesnoth=str(ROOT/'.runtime/install/bin/wesnoth'), replay_path=folder/'game.json',
                experiment_deadline=time.time()+30,
                learning=dict(support=shared, sides={'1': {'teacher': False}}))
    results['watchdog'] = result
    assert result['reason'] == 'watchdog_timeout' and result['faults'], result
    assert 'teacher query' in result['faults'][1], result
    print(json.dumps(dict(case='watchdog', expected_fault=result['faults'])), flush=True)
    write_json(args.output/'summary.json', dict(passed=True, results=results, traces=traces))


if __name__ == '__main__':
    main()
