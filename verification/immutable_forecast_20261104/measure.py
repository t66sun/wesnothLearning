"""Apply the unchanged two final flags and compare with the same integrated baseline."""
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

from learning import sample


def main():
    output=Path(sys.argv[2]);probe=Path(__file__).resolve().parents[1]/'vision_footprint_20261104/measure_views.py'
    original=sample.play_job
    def final(job):
        assert job['id']=='val000010-team2v2-b0000-astra_partner-r0' and job['seed']==2791729219
        assert job['meta']['map_partition']=='validation' and job['score_only_astra']
        assert not job.get('learning') and not job.get('shard') and not job.get('learner_sides')
        job['score_only_policy']=True
        (output/'requirements.json').write_text(json.dumps(dict(source=os.environ['SOURCE_COMMIT'],
            baseline_source='7889264e74a5151ebd21d7185f7b220662818c37',baseline_cpu=17.010085134,
            minimum_cpu_reduction=.06,real_games=1,score_only_astra=True,score_only_policy=True),indent=2)+'\n')
        return original(job)
    with patch.object(sample,'play_job',final): runpy.run_path(str(probe),run_name='__main__')
    view=json.loads((output/'views.json').read_text());profile=json.loads((output/'profile.json').read_text())
    assert view['decisions']==1031 and view['view_batches']*4==4128
    assert view['all_side_views_sha256']=='480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd'
    assert profile['action_event_sha256']=='3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1'


if __name__=='__main__':main()
