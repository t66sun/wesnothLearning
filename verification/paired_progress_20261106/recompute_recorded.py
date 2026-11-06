"""Recompute frozen BC/latest evidence; selected has no matched replies here."""
import argparse
import copy
import json
import math
from pathlib import Path

from learning.common import read_json, sha256
from learning.progress import checkpoint_roles, paired_progress


def recompute(run, anchor):
    old_plan = read_json(anchor/'plan.json')
    old_summary = read_json(anchor/'summary.json')
    old_identities = read_json(anchor/'identities.json')
    bc_results = [json.loads(line) for line in (anchor/'results.jsonl').read_text().splitlines()]
    report = dict(scope='read-only recomputation; zero new games; selected is unmeasured on these cells',
        inputs={name: sha256(anchor/name) for name in ('plan.json', 'summary.json', 'identities.json', 'results.jsonl')},
        formats={})
    for fmt, original in old_plan.items():
        roles = checkpoint_roles(run/fmt)
        for role in ('bc', 'latest'):
            assert roles[role]['checkpoint_sha256'] == old_identities[fmt][role+'_checkpoint_sha256']
        jobs = []
        for role in ('bc', 'latest'):
            for source in original[role]:
                job = copy.deepcopy(source)
                job['meta']['progress_role'] = role
                jobs.append(job)
        # Empty matched selected cells explicitly expose the absence of its
        # validation evidence. No holdout reply is ever substituted for them.
        for source in original['latest']:
            job = copy.deepcopy(source)
            job['id'] = 'unmeasured-selected-'+job['id']
            job['meta']['progress_role'] = 'selected'
            for side in job['meta']['policy_sides']:
                job['bots'][side-1] = 'unmeasured-selected'
            jobs.append(job)
        ids = {job['id'] for job in original['latest']}
        log = run/fmt/'jobs.jsonl'
        with log.open() as stream:
            latest_results = [row for line in stream if (row := json.loads(line))['id'] in ids]
        result = paired_progress(jobs, latest_results+bc_results, fmt, 12)
        expected = old_summary['formats'][fmt]['paired_latest_minus_bc_normalized_policy_score']
        assert math.isclose(result['latest']['difference'], expected['mean'], abs_tol=1e-12)
        assert all(math.isclose(a, b, abs_tol=1e-12)
                   for a, b in zip(result['latest']['interval95'], expected['interval95']))
        assert result['latest']['complete'] and result['latest']['distinct_scenarios'] == 12
        assert not result['selected']['complete'] and result['selected']['missing_blocks'] == 12
        report['formats'][fmt] = dict(checkpoint_roles=roles, jobs_sha256=sha256(log), progress=result)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('anchor', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = recompute(args.run, args.anchor)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    for fmt, row in result['formats'].items():
        print(fmt, json.dumps(row['progress']['latest']))
