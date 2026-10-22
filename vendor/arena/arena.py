"""Native Wesnoth SDK entry point; series are headless, play uses the real UI."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import math
import subprocess
import sys
import addons
import native
import params as P
from match import play_game


def positive_int(value):
    value=int(value)
    if value<1: raise argparse.ArgumentTypeError('must be positive')
    return value


def positive_float(value):
    value=float(value)
    if not math.isfinite(value) or not 0<value<=3600:
        raise argparse.ArgumentTypeError('must be finite, positive, and <=3600')
    return value


def seed_value(value):
    value=int(value)
    if not 0<=value<=0xffffffff: raise argparse.ArgumentTypeError('seed must be uint32')
    return value


def add_options(parser):
    parser.add_argument('--wesnoth')
    parser.add_argument('-j',type=positive_int,default=P.MAX_JOBS,help='parallel native games, capped at 4')
    parser.add_argument('--timeout',type=positive_float,default=P.ACTION_TIMEOUT)
    parser.add_argument('--first-timeout',type=positive_float,default=P.FIRST_TIMEOUT)
    parser.add_argument('--max-turns',type=positive_int,default=P.MAX_TURNS)
    parser.add_argument('--seed',type=seed_value,default=1)
    parser.add_argument('--no-fog',action='store_true',help='debug only')


def run_jobs(jobs, workers):
    with ThreadPoolExecutor(max_workers=min(P.MAX_JOBS,max(1,workers))) as pool:
        futures={pool.submit(play_game,**job['kwargs']):job['id'] for job in jobs}
        for future in as_completed(futures):
            result=future.result();ident=futures[future]
            print(f'{ident}: winner={result["winner"]} turns={result["turns"]} bots={result["bots"]} faults={result["faults"]}',flush=True)
            yield ident,result


def series(args):
    n=len(args.bots)
    if n not in P.PLAYERS or (args.mode=='match' and n!=2):
        raise ValueError('match needs 2 bots; ffa needs 4 or 8 bots')
    count=args.n or (P.GAMES if n==2 else n)
    exe=native.find_wesnoth(args.wesnoth)
    out=Path(args.replays or native.ROOT/'replays'/f'series_{__import__("time").time_ns()}')
    out.mkdir(parents=True,exist_ok=False)
    jobs=[]
    for i in range(count):
        rotation=i%n;block=i//n
        bots=args.bots[rotation:]+args.bots[:rotation]
        fs=[P.FACTIONS[(block*n+s)%6] for s in range(n)]
        jobs.append({'id':i+1,'kwargs':dict(bots=bots,seed=(args.seed+block)&0xffffffff,factions=fs,
            timeout=args.timeout,first_timeout=args.first_timeout,max_turns=args.max_turns,lenient=args.lenient,
            replay_path=str(out/f'game_{i+1:04}.json'),fog=not args.no_fog,wesnoth=exe)})
    results=[r for _,r in sorted(run_jobs(jobs,args.j))]
    wins={label:0 for r in results for label in r['bots']};draws=0
    for result in results:
        if result['winner']: wins[result['bots'][result['winner']-1]]+=1
        else: draws+=1
    summary=dict(rules_version=P.RULES_VERSION,games=results,wins=wins,draws=draws)
    target=Path(args.json) if args.json else out/'results.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'wins':wins,'draws':draws,'output':str(out)},ensure_ascii=False))
    return int(any(r['faults'] for r in results))


def replay(path, wesnoth=None):
    import tempfile
    import shutil
    exe=native.find_wesnoth(wesnoth)
    path=Path(path).resolve()
    if not path.is_file(): raise ValueError('replay file does not exist')
    with tempfile.TemporaryDirectory(prefix='wesnoth-replay-') as temp:
        user=Path(temp)
        shutil.copytree(native.ROOT/'runtime',user/'data/add-ons/arena_runtime')
        (user/'saves').mkdir()
        saved=user/'saves'/('arena_replay'+''.join(path.suffixes))
        shutil.copyfile(path,saved)
        return subprocess.call([exe,'--userdata-dir',str(user),'--usercache-dir',str(user/'cache'),
            '--load',saved.name,'--with-replay','--no-log-to-file',*native.console_options(),'--nosound'])


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    argv=sys.argv[1:] if argv is None else argv
    if not argv:
        from gui import main as gui_main
        gui_main();return 0
    if argv[0]=='tournament' and (native.ROOT/'tournament.py').exists():
        from tournament import main as tournament_main
        return tournament_main(argv[1:])
    parser=argparse.ArgumentParser(description='Wesnoth native WML/Lua Arena v2')
    sub=parser.add_subparsers(dest='mode',required=True)
    for name in ('match','ffa'):
        p=sub.add_parser(name);p.add_argument('bots',nargs=2 if name=='match' else '+')
        p.add_argument('-n',type=positive_int);p.add_argument('--lenient',action='store_true')
        p.add_argument('--replays');p.add_argument('--json');add_options(p)
    p=sub.add_parser('doctor');p.add_argument('--wesnoth')
    p=sub.add_parser('new');p.add_argument('name');p.add_argument('--output',default='submissions')
    p=sub.add_parser('validate');p.add_argument('bot')
    p=sub.add_parser('pack');p.add_argument('bot');p.add_argument('--output',required=True)
    p=sub.add_parser('install');p.add_argument('bot');p.add_argument('--userdata');p.add_argument('--wesnoth')
    p=sub.add_parser('play');p.add_argument('bot');p.add_argument('--players',type=int,choices=P.PLAYERS,default=2)
    p.add_argument('--side',type=int,default=2);p.add_argument('--wesnoth');p.add_argument('--seed',type=seed_value,default=1)
    p=sub.add_parser('replay');p.add_argument('file');p.add_argument('--wesnoth')
    args=parser.parse_args(argv)
    try:
        if args.mode in ('match','ffa'): return series(args)
        if args.mode=='doctor':
            exe=native.find_wesnoth(args.wesnoth)
            print('OK:',P.WESNOTH_VERSION,exe);print('Userdata:',native.userdata_path(exe));return 0
        if args.mode=='new': print(addons.create(args.name,args.output))
        elif args.mode=='validate':
            with addons.open_addon(args.bot) as addon: print('OK:',addons.validate(addon))
        elif args.mode=='pack': print(addons.pack(args.bot,args.output))
        elif args.mode=='install':
            user=Path(args.userdata) if args.userdata else native.userdata_path(native.find_wesnoth(args.wesnoth))
            print('Installed:',addons.install(args.bot,user))
            print('Restart Wesnoth; Local Multiplayer -> enable Arena AI modification -> select AI.')
        elif args.mode=='play':
            if not 1<=args.side<=args.players: raise ValueError('invalid bot side')
            human=1 if args.side!=1 else 2
            bots=['baseline']*args.players;bots[args.side-1]=args.bot
            result=play_game(bots,seed=args.seed,wesnoth=args.wesnoth,visible=True,human_side=human)
            print(json.dumps(result,ensure_ascii=False))
        elif args.mode=='replay': return replay(args.file,args.wesnoth)
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__=='__main__': raise SystemExit(main())
