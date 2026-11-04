"""One validation game with the integrated final flags and paired public-view checks."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import runpy
import sys
from time import monotonic,thread_time
from unittest.mock import patch

from learning import sample
from learning.lite_host import LiteHost
from learning.lite_policy import FrozenPolicies


def main():
    output=Path(sys.argv[2]);wrapper=Path(__file__).resolve().parents[1]/'vision_footprint_20261104/measure_views.py'
    play,decision,choose=sample.play_job,LiteHost.decision,FrozenPolicies.choose
    core=None;choices=0;cpu=wall=0.
    def final_job(job):
        assert job['id']=='val000010-team2v2-b0000-astra_partner-r0' and job['seed']==2791729219
        assert job['meta']['map_partition']=='validation' and job['score_only_astra'] and not job.get('learning')
        job['score_only_policy']=True
        (output/'plan.json').write_text(json.dumps(dict(source=os.environ['SOURCE_COMMIT'],game=job['id'],
            seed=job['seed'],score_only_astra=True,score_only_policy=True,real_games=1,
            baseline_cpu=17.010085134,baseline_wall=17.012544048950076,expected_public_views=4128),indent=2)+'\n')
        return play(job)
    def hold_core(host,side,**options):
        nonlocal core
        core=host.adapter.core
        return decision(host,side,**options)
    def timed_choice(policies,row,side,bootstrap=False):
        nonlocal cpu,wall,choices
        w,c=monotonic(),thread_time();value=choose(policies,row,side,bootstrap=bootstrap)
        cpu+=thread_time()-c;wall+=monotonic()-w;choices+=1;return value
    with ExitStack() as stack:
        for obj,attr,f in ((sample,'play_job',final_job),(LiteHost,'decision',hold_core),(FrozenPolicies,'choose',timed_choice)):
            stack.enter_context(patch.object(obj,attr,f))
        runpy.run_path(str(wrapper),run_name='__main__')
    data=json.loads(core.diagnostic_costs());data['policy_choice']=dict(calls=choices,cpu=cpu,wall=wall)
    (output/'costs.json').write_text(json.dumps(data,indent=2)+'\n')
    views=json.loads((output/'views.json').read_text());profile=json.loads((output/'profile.json').read_text())
    assert views['decisions']==1031 and views['view_batches']*4==4128
    assert views['all_side_views_sha256']=='480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd'
    assert profile['status']=='complete' and profile['action_event_sha256']=='3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1'
    print('SCOPE COUNT',len(data['scopes']),'EDGES',len(data['edges']),'POLICY',data['policy_choice'])


if __name__=='__main__':main()
