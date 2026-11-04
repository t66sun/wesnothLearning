"""Measure the frozen v10 team validation trace with both production final scoring paths."""
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

from learning import sample


def main():
    output = Path(sys.argv[2])
    reference = Path(__file__).resolve().parents[1]/'vision_footprint_20261104/measure_views.py'
    original = sample.play_job

    def final_job(job):
        assert job['id']=='val000010-team2v2-b0000-astra_partner-r0' and job['seed']==2791729219
        assert job['meta']['map_partition']=='validation' and job['score_only_astra']
        assert not job.get('learning') and not job.get('shard') and not job.get('learner_sides')
        job['score_only_policy']=True
        (output/'requirements.json').write_text(json.dumps(dict(source=os.environ['SOURCE_COMMIT'],
            baseline_release='fa0519eb3e5c8eced558e00598046950ae2edb8a2c0cd5f9352ccf7f84a13d69',
            real_games=1, minimum_cpu_reduction=.05, score_only_astra=True, score_only_policy=True,
            seat='team2v2/astra_partner/r0', expected_commits=1031, expected_public_views=4128),indent=2)+'\n')
        return original(job)

    with patch.object(sample, 'play_job', final_job):
        runpy.run_path(str(reference),run_name='__main__')
    view=json.loads((output/'views.json').read_text())
    assert view['decisions']==1031 and view['view_batches']*4==4128
    assert view['all_side_views_sha256']=='480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd'
    summary=json.loads((output/'profile.json').read_text())
    assert summary['action_event_sha256']=='3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1'


if __name__=='__main__':main()
