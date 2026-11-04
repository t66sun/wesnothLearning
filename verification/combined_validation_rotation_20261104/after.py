"""Run the frozen 14-game validation rotation once with both final-panel scoring paths."""
import json
import os
import sys
import tarfile
from pathlib import Path
from unittest.mock import patch

from learning.common import sha256
from learning.data import keeps_behavior, keeps_reward_diagnostics

BASE = Path(__file__).resolve().parents[1] / 'lite_panel_throughput_20261104'
sys.path.insert(0, str(BASE))
import probe as frozen

ARCHIVE_HASH = '1a45922ea8ec78fc5c88b38c71e5977d842d1ed42b8caae85bb3d1ef52454f95'
STRICT = {
    ('duel', 'solo'): (26.37, 60),
    ('ffa4', 'solo'): (18.58, 120),
    ('team2v2', 'astra_partner'): (21.33, 120),
    ('team2v2', 'self_team'): (32.25, 120),
}


def main():
    original_collect = frozen.sample.collect

    def combined(jobs, workers, log_path):
        output = Path(log_path).parent
        archive = BASE / 'rotation.tar.gz'
        assert sha256(archive) == ARCHIVE_HASH
        with tarfile.open(archive, 'r:gz') as baseline:
            old_plan = json.load(baseline.extractfile('panel/plan.json'))
            old = {r['id']: r for r in map(json.loads, baseline.extractfile('panel/jobs.jsonl'))}
        plan = json.loads((output / 'plan.json').read_text())
        for key in ('games', 'inputs', 'workers', 'deadline_seconds', 'rules_sha256', 'teacher_sha256', 'max_turns', 'selection'):
            assert plan[key] == old_plan[key], key
        assert plan['source'] == os.environ['SOURCE_COMMIT']
        assert plan['extension_sha256'] == os.environ['EXTENSION_SHA256']
        assert [j['id'] for j in jobs] == [g['id'] for g in old_plan['games']]
        for j in jobs:
            assert j['engine'] == 'lite' and j['meta']['map_partition'] == 'validation' and j['score_only_astra']
            assert not j.get('learning') and not j.get('shard') and not j.get('learner_sides')
            assert not keeps_behavior(j['meta']) and not keeps_reward_diagnostics(j['meta'])
            j['score_only_policy'] = True
        (output / 'comparison-plan.json').write_text(json.dumps(dict(
            archived_baseline_sha256=ARCHIVE_HASH, source=plan['source'], source_archive_sha256=os.environ['SOURCE_ARCHIVE_SHA256'],
            extension_sha256=plan['extension_sha256'], score_only_astra=True, score_only_policy=True,
            strict_rates={fmt + '/' + ctx: dict(mean_seconds=mean, games=count) for (fmt, ctx), (mean, count) in STRICT.items()},
            workers=workers, target_seconds=864, after_only=True), indent=2) + '\n')
        results = original_collect(jobs, workers, log_path)
        actual = {r['id']: r for r in results}
        complete = (actual.keys() == old.keys() and len(results) == len(old) == 14
                    and all(r.get('status') == 'complete' and not r.get('result', {}).get('faults')
                            and r.get('result') == old[r['id']]['result'] for r in results))
        groups = {}
        weighted = 0.
        for (fmt, context), (mean, count) in STRICT.items():
            ids = [j['id'] for j in old_plan['games'] if j['format'] == fmt and j['context'] == context]
            old_time = sum(old[i]['probe']['end'] - old[i]['probe']['start'] for i in ids)
            new_time = sum(actual[i]['probe']['end'] - actual[i]['probe']['start'] for i in ids
                           if i in actual and 'probe' in actual[i])
            ratio = new_time / old_time if complete else None
            groups[fmt + '/' + context] = dict(games=len(ids), baseline_worker_seconds=old_time,
                                               after_worker_seconds=new_time, after_over_before=ratio)
            if complete:
                weighted += mean * count * ratio
        report = dict(all_official_results_match=complete, groups=groups, strict_uncorrected_seconds=1280.175,
                      projected_strict_seconds=weighted / workers if complete else None, target_seconds=864)
        (output / 'combined.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report), flush=True)
        if not complete:
            raise AssertionError('combined scoring did not reproduce all 14 archived official outcomes')
        return results

    with patch.object(frozen.sample, 'collect', combined):
        frozen.main()


if __name__ == '__main__':
    main()
