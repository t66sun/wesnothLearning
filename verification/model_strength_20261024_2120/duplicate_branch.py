"""Read-only comparison of retained tensors across the two continuations."""
from pathlib import Path
import torch
import json

torch.set_num_threads(1)
parent=Path('../validation_memory_repair_20261024_1321/runs/v5_lite_resume_20261024_1420')
current=Path('runs/v5_lite_windowfix_20261024_1630')
for fmt,versions in (('duel',(110,200)),('ffa4',(110,))):
    for v in versions:
        relative=Path(fmt)/'policies'/f'v{v:06}-greedy/model.pt'
        old=torch.load(parent/relative,map_location='cpu',weights_only=False)['model']
        new=torch.load(current/relative,map_location='cpu',weights_only=False)['model']
        print('DUPLICATE',fmt,v,'all_tensors_equal',all(torch.equal(old[k],new[k]) for k in old),'max_difference',max(float((old[k]-new[k]).abs().max()) for k in old))
