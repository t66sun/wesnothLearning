"""Hash every public view and count repeat vision origins on the archived validation game."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

from learning.lite_host import LiteHost


def main():
    output = Path(sys.argv[2])
    profiler = Path(__file__).resolve().parents[1]/'lite_final_worker_20261104/profile_job.py'
    execute = LiteHost.execute
    seen = None
    decisions = origins = unchanged = 0
    views = hashlib.sha256()

    def capture(host):
        nonlocal seen, origins, unchanged
        encoded = host.adapter.core.observe_batch('[1,2,3,4]')
        views.update(encoded.encode() + b'\n')
        current = {u['id']:(u['unit_type'],u['pos']) for side in json.loads(encoded)
                   for u in side['units'] if u['side']==side['side']}
        origins += len(current)
        if seen is not None:
            unchanged += sum(seen.get(ident)==value for ident,value in current.items())
        seen = current

    def observed_execute(host, action, **opts):
        nonlocal decisions
        if seen is None:
            capture(host)
        outcome = execute(host, action, **opts)
        if outcome['committed']:
            capture(host)
            decisions += 1
        return outcome

    with patch.object(LiteHost, 'execute', observed_execute):
        runpy.run_path(str(profiler), run_name='__main__')
    (output/'views.json').write_text(json.dumps(dict(decisions=decisions, view_batches=decisions+1,
        all_side_views_sha256=views.hexdigest(), candidate_footprints=origins,
        same_type_and_position=unchanged, unchanged_fraction=unchanged/origins), indent=2))


if __name__ == '__main__':
    main()
