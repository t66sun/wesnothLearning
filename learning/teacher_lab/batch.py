"""Compare several frozen challengers using one shared native worker pool."""
import argparse
import json
from pathlib import Path
import time
from learning.formats import FORMATS
from learning.teacher_lab.__main__ import candidate, clock
from learning.teacher_lab.packages import digest, read, require_evaluator
from learning.teacher_lab.panels import HORIZONS, execute, jobs_for
from learning.teacher_lab.report import report_panel


def batch(args):
    manifest=read(args.directory/'manifest.json');require_evaluator(manifest)
    deadline=clock(args.directory)['exploration_end']
    if time.time()>=deadline:
        raise ValueError('exploration deadline expired')
    if args.blocks<1 or args.offset<0 or len(args.candidates)!=len(set(args.candidates)):
        raise ValueError('positive blocks, nonnegative offset and distinct candidates are required')
    control=manifest['baseline']
    if digest(control['package'])!=control['package_sha256']:
        raise ValueError('frozen baseline package changed')
    chosen=[candidate(args.directory,name) for name in args.candidates]
    directory=args.directory/'panels'/args.name
    jobs=[job for row in chosen for fmt in args.formats for horizon in HORIZONS
          for job in jobs_for(directory,row,control,fmt,horizon,args.blocks,'train',deadline,
                              manifest['executable'],seed=args.seed,offset=args.offset)]
    results=execute(directory,jobs,workers=manifest['workers'],metadata=dict(
        partition='train',source_commit=manifest['source_commit'],runner_sha256=digest(__file__),
        candidates={row['name']:row['package_sha256'] for row in chosen},
        control_sha256=control['package_sha256']))
    return report_panel(directory,jobs,results)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--name',required=True)
    parser.add_argument('--candidates',required=True,nargs='+')
    parser.add_argument('--formats',nargs='+',choices=FORMATS,default=FORMATS)
    parser.add_argument('--blocks',type=int,default=1)
    parser.add_argument('--offset',type=int,default=0)
    parser.add_argument('--seed',type=int,default=20261107)
    args=parser.parse_args();args.directory=args.directory.resolve()
    print(json.dumps(batch(args),indent=2),flush=True)


if __name__=='__main__':
    main()
