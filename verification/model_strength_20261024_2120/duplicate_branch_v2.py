from pathlib import Path
import torch

torch.set_num_threads(1)
roots=[Path('../validation_memory_repair_20261024_1321/runs/v5_lite_resume_20261024_1420'),Path('../validation_training_repair_20261023_194022/runs/v5_lite18h_20261024_003512')]
current=Path('runs/v5_lite_windowfix_20261024_1630')
for fmt,versions in (('duel',(110,200)),('ffa4',(110,))):
    for v in versions:
        relative=Path(fmt)/'policies'/f'v{v:06}-greedy/model.pt'
        source=next((root/relative for root in roots if (root/relative).exists()),None)
        if source is None:print('MISSING',fmt,v);continue
        old=torch.load(source,map_location='cpu',weights_only=False)['model']
        new=torch.load(current/relative,map_location='cpu',weights_only=False)['model']
        print('DUPLICATE',fmt,v,'source',str(source),'all_tensors_equal',all(torch.equal(old[k],new[k]) for k in old),'max_difference',max(float((old[k]-new[k]).abs().max()) for k in old))
