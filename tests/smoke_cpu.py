"""One local CPU smoke: real model updates/checkpoints, simulated game jobs."""
from pathlib import Path
from multiprocessing import get_context
from unittest.mock import patch
import argparse,json,random,time
from learning.common import ROOT,write_json


def simulated_game(job):
    time.sleep(.15)
    return dict(id=job['id'],status='complete')


def trainer(fmt,directory,config,manifest,requests,replies):
    import torch
    from learning.experiment import FormatExperiment
    from learning.features import GLOBAL,OPPONENT,ACTION,VERSION
    from learning.data import split
    from learning.model import Policy,batch
    from learning.train import train,checkpoint,restore_rng
    from learning.export import load_model
    torch.set_num_threads(config['trainer_threads']);torch.manual_seed(13)
    forbidden=AssertionError('CPU smoke must not access CUDA RNG or availability')
    with patch('torch.cuda.is_available',side_effect=forbidden),patch('torch.cuda.get_rng_state_all',side_effect=forbidden),patch('torch.cuda.set_rng_state_all',side_effect=forbidden):
        # The actual trainer initialization/export/hardware path, on CPU.
        exp=FormatExperiment(Path(directory)/fmt,fmt,manifest,dict(started=time.time(),update_deadline=time.time()+60,deadline=time.time()+120),None)
        assert exp.device=='cpu' and torch.get_num_threads()==1
        family=next('cpu-smoke-'+str(i) for i in range(100) if split('cpu-smoke-'+str(i))=='train')
        rng=random.Random(7);records=[]
        for i in range(4):
            records.append(dict(schema=VERSION,format=fmt,source='astra',teacher='gpt6astra',version='smoke',game_id=family,
                game_family=family,split='train',side=1,turn=i,value=0.,reward=1.,value_valid=True,choice=0,
                log_probability=0.,**{'global':[0.]*len(GLOBAL)},opponents=[[0.]*len(OPPONENT)],
                candidates=[dict(features=[rng.random() for _ in ACTION[:-1]]+[0]) for _ in range(8)]))
        before=exp.model.scorer[0].weight.detach().clone()
        bc=train(exp.model,exp.optimizer,records,'bc',epochs=1,minibatch=4)
        assert bc['updates']==1 and not torch.equal(before,exp.model.scorer[0].weight)
        with torch.no_grad():
            logits,values=exp.model(*batch(records,'cpu'))
        ppo=[dict(r,teacher=False,source='policy',log_probability=float(torch.log_softmax(logits[i],0)[0]),value=float(values[i])) for i,r in enumerate(records)]
        reinforcement=train(exp.model,exp.optimizer,ppo,'ppo',epochs=1,minibatch=4,bc_records=records)
        path=Path(directory)/fmt/'cpu_smoke.pt';checkpoint(path,exp.model,exp.optimizer)
        restored,state=load_model(path,fmt,'cpu');restore_rng(state,'cpu')
        assert not state['cuda_rng'] and all(torch.equal(v,restored.state_dict()[k]) for k,v in exp.model.state_dict().items())
        resumed=FormatExperiment(Path(directory)/fmt,fmt,manifest,exp.clock,None,resume=True)
        assert resumed.device=='cpu' and resumed.state['clock']==exp.clock
        write_json(Path(directory)/fmt/'smoke.json',dict(device=exp.device,threads=torch.get_num_threads(),bc=bc,ppo=reinforcement,checkpoint_restored=True))
        jobs=[dict(id=f'cpu-{fmt}-{i}',deadline=time.time()+60) for i in range(4)]
        requests.put((fmt,jobs,str(Path(directory)/(fmt+'.jobs.jsonl'))))
        result=replies.get(timeout=90)['results'];assert len(result)==4 and all(r['status']=='complete' for r in result)


def main():
    from learning.__main__ import parser,run_config
    from learning.experiment import default_config,validate_config
    from learning.coordinator import broker
    from learning.formats import FORMATS
    p=argparse.ArgumentParser();p.add_argument('--output',default='verification/cpu_smoke_20261018');args=p.parse_args()
    config=run_config(parser().parse_args(['run','--device','cpu','--workers','4']))
    assert (config['device'],config['workers'],config['trainer_threads'])==('cpu',4,1)
    assert default_config('cpu')['workers']==8
    cuda=run_config(parser().parse_args(['run']));assert (cuda['device'],cuda['workers'],cuda['trainer_threads'])==('cuda',8,1)
    assert run_config(parser().parse_args(['run','--device','cpu','--workers','2']))['workers']==2
    validate_config(config)
    out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=False)
    manifest=dict(config=config,opponents=[dict(path=str(ROOT/'data/opponents/gpt6astra.zip'))],baseline=dict(path='simulated-no-game'))
    write_json(out/'manifest.json',manifest)
    ctx=get_context('spawn');requests=ctx.Queue();replies={f:ctx.Queue() for f in FORMATS};processes={}
    try:
        for fmt in FORMATS:
            proc=ctx.Process(target=trainer,args=(fmt,str(out),config,manifest,requests,replies[fmt]));processes[fmt]=proc;proc.start()
        metrics=broker(processes,requests,replies,config['workers'],out,play=simulated_game)
        for proc in processes.values():proc.join(10)
        assert all(proc.exitcode==0 for proc in processes.values()),metrics
        assert metrics['peak_native_games']==4,metrics
        result=dict(passed=True,device='cpu',workers=4,trainer_threads=1,native_games_started=0,simulated_jobs=12,
            scheduler=metrics,formats={f:json.loads((out/f/'smoke.json').read_text()) for f in FORMATS})
        write_json(out/'summary.json',result);print(json.dumps(result,indent=2))
    finally:
        for proc in processes.values():
            if proc.is_alive():proc.terminate();proc.join()
        requests.close()
        for reply in replies.values():reply.close()


if __name__=='__main__':main()
