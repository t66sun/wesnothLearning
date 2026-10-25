"""CLI entry points. --help and report/package never launch Wesnoth."""
import argparse
from pathlib import Path
import json
import os
import sys
from .common import ROOT, read_json, write_json
from .formats import FORMATS


def parser():
    p=argparse.ArgumentParser(description='WesnothLearning V5: native/lite、序列 BC/DAgger/PPO 与 Lua 部署')
    commands=p.add_subparsers(dest='command',required=True)
    run=commands.add_parser('run',help='运行或恢复有固定截止时间的完整实验')
    run.add_argument('--run-dir',default='runs/first');run.add_argument('--resume',metavar='RUN_DIR',help='恢复原目录冻结的设备、进程数和截止时间')
    run.add_argument('--branch-from',metavar='RUN_DIR',help='从另一实验的 latest.pt 建立显式分支（新目录、新预算，保留父记录）')
    run.add_argument('--branch-reset-optimizer',action='store_true',help='分支时只保留权重，重新初始化 Adam')
    run.add_argument('--hours',type=float,default=12);run.add_argument('--workers',type=int,default=None,help='全局游戏进程数（1–16；默认 8）')
    run.add_argument('--formats',nargs='+',choices=FORMATS,default=list(FORMATS))
    run.add_argument('--human-data',default=str(ROOT/'data/datasets/human'))
    run.add_argument('--device',default='cpu',help='cpu / cuda / cuda:0 / auto')
    run.add_argument('--engine',choices=['native','lite'],default=None,help='默认 lite；采样和最终评测均跟随此引擎')
    run.add_argument('--evaluation-engine',choices=['native','lite'],default=None,help='最终评测引擎，默认跟随 --engine')
    run.add_argument('--rules-dir',help='冻结规则目录，默认 data/rules/1.18.8-training；恢复时使用 manifest')
    run.add_argument('--reward-mode',choices=['fixed','scheduled','adaptive'],default='adaptive')
    run.add_argument('--phase',choices=['auto','bc'],default=None,help='auto 一键流程；bc 只做 BC，完成后等待显式 PPO/评测指令')
    run.add_argument('--allow-approximate',action=argparse.BooleanOptionalAction,default=None,help='lite 默认接受已记录近似；不允许未支持的训练单位')
    run.add_argument('--trainer-threads',type=int,default=1,help='每个训练器的 CPU 计算线程数（默认 1）')
    run.add_argument('--wesnoth');run.add_argument('--opponents',default=str(ROOT/'data/opponents'))
    run.add_argument('--seed',type=int,default=20261017);run.add_argument('--final-blocks',type=int,default=30)
    run.add_argument('--final-holdout-hours',type=float,help='在原最终评估预算内为 holdout 预留小时数；默认 0，提名提前截止')
    run.add_argument('--validation-interval',type=int,default=10,help='每多少轮采集并更新参数后进行一次同引擎对局验证')
    run.add_argument('--bc-games',nargs=3,type=int,metavar=('DUEL','FFA4','TEAM2V2'),help='有效教师对局总目标，单挑/FF4/2v2 默认 300/600/400；lite 默认全部使用 lite')
    run.add_argument('--native-bc-games',nargs=3,type=int,metavar=('DUEL','FFA4','TEAM2V2'),help='各赛制原版教师局数下限，计入 --bc-games；lite 默认 0 0 0，native 默认 300 600 400')
    run.add_argument('--bc-batch-games',type=int,help='每个赛制每轮采集的教师局数（默认 8，共享全局进程池）')
    run.add_argument('--bc-records',type=int,help='轮换教师训练样本池容量（CPU 默认 2048，CUDA 默认 8192）')
    run.add_argument('--bc-validation-records',type=int,help='固定验证样本池容量（CPU 默认 1024，CUDA 默认 4096）')
    run.add_argument('--shaping-weight',type=float,help='训练潜势差分权重（默认 0.05；设 0 可关闭）')
    phase=commands.add_parser('phase',help='在批次边界切换 BC/PPO/最终评测；停止的实验需随后 resume')
    phase.add_argument('phase',choices=['show','auto','bc','ppo','evaluate'])
    phase.add_argument('--run-dir',required=True)
    phase.add_argument('--formats',nargs='+',choices=FORMATS,help='默认该实验的全部赛制')
    phase.add_argument('--force',action='store_true',help='仅 PPO：明确跳过未通过的 BC 资格门，不改写门结果')
    phase.add_argument('--reason',default='')
    phase.add_argument('--hours',type=float,help='显式分配本阶段预算；不修改原 clock/manifest，省略沿用原剩余预算')
    collect=commands.add_parser('collect',help='执行固定 JSON 采样任务清单（启动游戏）')
    collect.add_argument('--jobs',required=True);collect.add_argument('--workers',type=int,default=8)
    collect.add_argument('--output',required=True)
    collect.add_argument('--engine',choices=['native','lite'],default='lite')
    collect.add_argument('--rules-dir')
    train=commands.add_parser('train',help='对现有分片进行一次 BC/PPO 更新')
    train.add_argument('--data',required=True);train.add_argument('--method',choices=['bc','ppo'],required=True)
    train.add_argument('--checkpoint');train.add_argument('--output',required=True)
    train.add_argument('--format',choices=FORMATS,required=True);train.add_argument('--bc-data',help='PPO 同赛制 BC 辅助数据目录')
    train.add_argument('--device',default='cuda');train.add_argument('--epochs',type=int,default=4)
    train.add_argument('--minibatch',type=int,default=256);train.add_argument('--threads',type=int,default=1)
    evaluate=commands.add_parser('evaluate',help='执行固定评测赛程（启动游戏）')
    evaluate.add_argument('--jobs',required=True);evaluate.add_argument('--workers',type=int,default=8)
    evaluate.add_argument('--output',required=True)
    evaluate.add_argument('--format',choices=FORMATS,required=True)
    evaluate.add_argument('--engine',choices=['native','lite'],default='native')
    evaluate.add_argument('--rules-dir')
    export=commands.add_parser('export',help='将检查点导出为 SDK 原生附加组件')
    for fmt in FORMATS: export.add_argument('--'+fmt,required=True,metavar='CHECKPOINT')
    export.add_argument('--output',required=True)
    export.add_argument('--audit-data',required=True,help='每赛制子目录中的实际当前schema连续序列（含128候选）')
    export.add_argument('--name',default='NeuralArena');export.add_argument('--mode',choices=['greedy','rule','sample'],default='greedy')
    report=commands.add_parser('report',help='只从已有结果重算区间（不启动游戏）')
    report.add_argument('--jobs',required=True);report.add_argument('--results',required=True);report.add_argument('--output',required=True)
    package=commands.add_parser('package',help='打包可传到 Linux 的开发工程')
    package.add_argument('--output',default='delivery/WesnothLearning.zip')
    bundle=commands.add_parser('bundle',help='构建可解压即用的 Ubuntu 24.04 训练归档')
    bundle.add_argument('--output',required=True,help='归档路径，须在工程目录内')
    bundle.add_argument('--wheel',help='可选 manylinux x86_64 wheel，复制到归档 dist/')
    bundle.add_argument('--created-at',help='ISO 8601 时间戳；固定后同一输入产生相同字节')
    verify=commands.add_parser('verify-bundle',help='静态校验训练归档的结构、哈希与权限')
    verify.add_argument('archive');verify.add_argument('--require-wheel',action='store_true',help='要求归档内含 manylinux x86_64 wheel')
    human=commands.add_parser('import-human',help='准备原版重放观测，或导入通过校验的 1.18.8 捕获日志')
    human.add_argument('--curated',default=str(ROOT/'data/humanData_curated'))
    human.add_argument('--output',default='data/datasets/human');human.add_argument('--wesnoth')
    human.add_argument('--inventory-only',action='store_true',help='仅生成兼容性清单，不启动游戏')
    human.add_argument('--captures',help='原版 1.18.8 完整重放日志目录，文件名 game_NNNN.log')
    control=commands.add_parser('control',help='每赛制批次边界应用的在线配置')
    sub=control.add_subparsers(dest='control_command',required=True)
    show=sub.add_parser('show');show.add_argument('--run-dir',required=True)
    setter=sub.add_parser('set');setter.add_argument('--run-dir',required=True)
    setter.add_argument('--format',choices=FORMATS,required=True)
    setter.add_argument('--reward-mode',choices=['fixed','scheduled','adaptive'])
    for name in ('economy','control','explore'): setter.add_argument('--reward-'+name,type=float)
    setter.add_argument('--entropy',type=float);setter.add_argument('--bc-aux',type=float)
    setter.add_argument('--reason',default='manual CLI update')
    audit=commands.add_parser('audit',help='现有数据的完整审计；不会自动训练')
    audits=audit.add_subparsers(dest='audit_command',required=True)
    bc=audits.add_parser('bc');bc.add_argument('--data',required=True);bc.add_argument('--format',choices=FORMATS,required=True);bc.add_argument('--output',required=True)
    fit=audits.add_parser('fit');fit.add_argument('--data',required=True);fit.add_argument('--format',choices=FORMATS,required=True)
    fit.add_argument('--checkpoint');fit.add_argument('--steps',type=int,default=1000);fit.add_argument('--output',required=True)
    bench=commands.add_parser('benchmark',help='引擎基准清单/已有结果报告')
    benches=bench.add_subparsers(dest='benchmark_command',required=True)
    engines=benches.add_parser('engines');engines.add_argument('--manifest',required=True);engines.add_argument('--results');engines.add_argument('--output',required=True)
    rules=commands.add_parser('rules',help='冻结原版 1.18.8 已导出的规则资料')
    rules.add_argument('--captures',nargs='+',required=True);rules.add_argument('--output',default='data/rules/1.18.8')
    map_command=commands.add_parser('freeze-map',help='从已确认1.18.8发行包导出原版地图')
    map_command.add_argument('--source',required=True);map_command.add_argument('--name',required=True)
    map_command.add_argument('--output',default='data/rules/1.18.8/maps')
    map_command.add_argument('--catalog',default='data/rules/1.18.8/catalog.json')
    return p


def bind_rules(args):
    """Resolve rules before importing feature/model modules, including resume."""
    from .rules_catalog import resolve_dir
    directory=getattr(args,'rules_dir',None)
    source=getattr(args,'resume',None) or getattr(args,'branch_from',None)
    if source:
        manifest=read_json(Path(source)/'manifest.json')
        frozen=manifest['config'].get('rules_dir',str(ROOT/'data/rules/1.18.8'))
        if directory and resolve_dir(directory)!=resolve_dir(frozen):
            raise ValueError('resume must use the frozen rules directory')
        directory=frozen
    directory=resolve_dir(directory)
    os.environ['WESNOTH_RULES_DIR']=str(directory)
    if 'learning.features' in sys.modules:
        sys.modules['learning.features'].select_rules(directory)
    return directory


def run_config(args):
    directory=bind_rules(args)
    from .experiment import default_config
    names=('hours','workers','device','trainer_threads','seed','final_blocks','formats','human_data','validation_interval',
           'bc_batch_games','bc_records','bc_validation_records','shaping_weight','engine','evaluation_engine','reward_mode','allow_approximate','phase','final_holdout_hours')
    config=default_config(args.device,engine=args.engine)|{name:getattr(args,name) for name in names if getattr(args,name) is not None}
    config['rules_dir']=str(directory)
    if args.bc_games is not None:config['bc_games']=dict(zip(FORMATS,args.bc_games))
    if args.native_bc_games is not None:config['native_bc_games']=dict(zip(FORMATS,args.native_bc_games))
    return config


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8')
    p=parser();args=p.parse_args(argv)
    try:
        bind_rules(args)
        from .manifest import output_path
        if args.command=='run':
            if args.resume and args.phase is not None: raise ValueError('resume keeps the saved phase; use phase --run-dir to change it')
            if args.resume and args.branch_from: raise ValueError('choose resume or branch, not both')
            if args.branch_from and Path(args.branch_from).resolve()==Path(args.run_dir).resolve(): raise ValueError('branch needs a new run directory')
            from .coordinator import Experiment
            config=run_config(args)
            if args.branch_from: config['branch_reset_optimizer']=bool(args.branch_reset_optimizer)
            result=Experiment(args.resume or args.run_dir,config=config,opponents=args.opponents,wesnoth=args.wesnoth,
                resume=bool(args.resume),branch_from=args.branch_from).run()
            print('Experiment:',result['status'])
        elif args.command=='phase':
            from .phases import request_phase,show_phases
            directory=output_path(args.run_dir)
            result=show_phases(directory) if args.phase=='show' else request_phase(directory,args.phase,
                formats=args.formats,force=args.force,reason=args.reason,hours=args.hours)
            print(json.dumps(result,ensure_ascii=False))
        elif args.command in ('collect','evaluate'):
            from .sample import collect
            jobs=read_json(args.jobs)
            if args.command=='evaluate' and any(j.get('meta',{}).get('format')!=args.format for j in jobs): raise ValueError('evaluation schedule format mismatch')
            for job in jobs:
                job['engine']=args.engine
                job['rules_dir']=str(bind_rules(args))
                if job['engine']=='lite': job.setdefault('allow_approximate',True)
                output_path(job['output'])
                if job.get('shard'): output_path(job['shard'])
            out=output_path(args.output);out.mkdir(parents=True,exist_ok=False)
            result=collect(jobs,args.workers,out/'jobs.jsonl')
            write_json(out/'results.json',result)
            if args.command=='evaluate':
                from .evaluate import control_comparisons
                write_json(out/'comparison.json',control_comparisons(jobs,result))
            print('Completed:',sum(r['status']=='complete' for r in result),'/',len(jobs))
        elif args.command=='train':
            import torch
            from .data import read_shards
            from .export import load_model
            from .model import Policy
            from .train import train, checkpoint, restore_rng
            torch.set_num_threads(args.threads)
            model,state=load_model(args.checkpoint,args.format,args.device) if args.checkpoint else (Policy(args.format).to(args.device),None)
            optimizer=torch.optim.Adam(model.parameters(),lr=1e-4 if args.method=='ppo' else 3e-4)
            if state:
                optimizer.load_state_dict(state['optimizer']);restore_rng(state,args.device)
            paths=sorted(Path(args.data).glob('*.jsonl.gz'))
            bc_paths=sorted(Path(args.bc_data).glob('*.jsonl.gz')) if args.bc_data else []
            metrics=train(model,optimizer,read_shards(paths,format_name=args.format),args.method,args.epochs,args.minibatch,
                bc_records=read_shards(bc_paths,format_name=args.format))
            checkpoint(output_path(args.output),model,optimizer,method=args.method,metrics=metrics,data_paths=[str(p) for p in paths])
            print(json.dumps(metrics))
        elif args.command=='export':
            from .export import export_checkpoints
            from .sequences import read_raw_shards
            if args.mode!='greedy': raise ValueError('delivery export uses greedy decisions')
            audit_records={fmt:read_raw_shards(sorted((Path(args.audit_data)/fmt).glob('*.jsonl.gz')),format_name=fmt) for fmt in FORMATS}
            print(export_checkpoints({fmt:getattr(args,fmt) for fmt in FORMATS},output_path(args.output),name=args.name,audit_records=audit_records))
        elif args.command=='report':
            from .evaluate import control_comparisons, overall_status
            from .experiment import read_log
            rows=read_json(args.results) if args.results.endswith('.json') else read_log(args.results)
            comparison=control_comparisons(read_json(args.jobs),rows)
            status=overall_status({f+'/'+c:v for f,controls in comparison.items() for c,v in controls.items()})
            write_json(output_path(args.output),dict(status=status,formats=comparison))
            print('Status:',status)
        elif args.command=='package':
            from .package import package_project
            print(package_project(output_path(args.output)))
        elif args.command=='bundle':
            from .bundle import build_bundle
            print(json.dumps(build_bundle(output_path(args.output),wheel=args.wheel,created_at=args.created_at),ensure_ascii=False))
        elif args.command=='verify-bundle':
            from .bundle import verify_bundle
            report=verify_bundle(args.archive,require_wheel=args.require_wheel)
            print(json.dumps(report,ensure_ascii=False))
            if not report['ok']: raise SystemExit(2)
        elif args.command=='import-human':
            from .human import import_curated
            result=import_curated(args.curated,output_path(args.output),args.wesnoth,args.inventory_only,args.captures)
            print(json.dumps({k:v for k,v in result.items() if k!='games'},ensure_ascii=False))
        elif args.command=='control':
            from .control import queue_control,show_control
            directory=output_path(args.run_dir)
            if args.control_command=='show': result=show_control(directory)
            else:
                changes={name:getattr(args,'reward_'+name) for name in ('economy','control','explore') if getattr(args,'reward_'+name) is not None}
                for name,argument in (('mode','reward_mode'),('entropy','entropy'),('bc_aux','bc_aux')):
                    if getattr(args,argument) is not None: changes[name]=getattr(args,argument)
                if not changes: raise ValueError('provide at least one control change')
                result=queue_control(directory,args.format,changes,reason=args.reason)
            print(json.dumps(result,ensure_ascii=False))
        elif args.command=='audit':
            from .audit import audit_bc,fit_small_set
            from .sequences import read_raw_shards
            rows=read_raw_shards(sorted(Path(args.data).glob('*.jsonl.gz')),format_name=args.format)
            if args.audit_command=='bc': result=audit_bc(rows)
            else:
                from .model import Policy
                from .export import load_model
                model=load_model(args.checkpoint,args.format)[0] if args.checkpoint else Policy(args.format)
                result=fit_small_set(model,rows,steps=args.steps)
            write_json(output_path(args.output),result)
            print(json.dumps(result,ensure_ascii=False))
        elif args.command=='benchmark':
            from .benchmark import benchmark_report
            result=benchmark_report(read_json(args.results) if args.results else [],read_json(args.manifest))
            write_json(output_path(args.output),result);print(json.dumps(result,ensure_ascii=False))
        elif args.command=='rules':
            from .rules import freeze_captures
            print(freeze_captures(args.captures,output_path(args.output)))
        elif args.command=='freeze-map':
            from .maps import freeze_map
            print(freeze_map(args.source,args.name,output_path(args.output),args.catalog))
    except (ValueError,FileExistsError,OSError) as exc:
        p.exit(2,str(exc)+'\n')


if __name__=='__main__': main()
