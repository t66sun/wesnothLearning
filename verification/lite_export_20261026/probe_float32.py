"""Read-only float32/float64/Lua comparison on the failed real prefix."""
from pathlib import Path
import copy
import json
import os
import sys

ROOT = Path('/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source')
RUN = ROOT / 'runs/v5_lite30h_20261025'
OUT = ROOT.parent / 'exports/lite_final_20261026_v2'
os.chdir(ROOT)
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor/arena')]
os.environ['WESNOTH_RULES_DIR'] = json.loads((RUN / 'manifest.json').read_text())['config']['rules_dir']
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
import torch
from lupa import LuaRuntime
import native
import learning.model as network_module
from learning.export import load_model, compact_lua, lua_parameters
from learning.sequences import read_raw_shards, sequence_key

torch.set_num_threads(1)
model, state = load_model(RUN / 'ffa4/selected.pt', 'ffa4')
model.eval()
double = copy.deepcopy(model).double().eval()
original_batch = network_module.batch
def convert(value):
    if isinstance(value, torch.Tensor):
        return value.double() if value.is_floating_point() else value
    if isinstance(value, dict):
        return {key:convert(item) for key,item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(convert(item) for item in value)
    return value
def double_batch(*args, **kwargs):
    return convert(original_batch(*args, **kwargs))
lua = LuaRuntime(unpack_returned_tuples=True)
source = (ROOT / 'lua/relational.lua').read_text()
source = source.replace('local M={}', "local M={}\nlocal function f32(v) return (string.unpack('f',string.pack('f',v))) end", 1)
source = source.replace('y[i]=relu and math.max(0,v) or v end;return y', 'y[i]=f32(relu and math.max(0,v) or v) end;return y', 1)
relational = lua.execute(source)
lua.globals().wesnoth = lua.table_from({'require':lambda path:relational})
network = lua.execute((ROOT / 'lua/network.lua').read_text())
weights = lua.eval(compact_lua(lua_parameters(model)))
memories = {}
rows = read_raw_shards([OUT / 'audit/ffa4.jsonl.gz'], format_name='ffa4')
results = []
with torch.no_grad():
    for row in rows:
        network_module.batch = original_batch
        tensors = original_batch([row])
        logits, value = model(*tensors)
        scene, _ = model.encode_scene(tensors[0], tensors[1], tensors[3], tensors[5])
        network_module.batch = double_batch
        dlogits, dvalue = double(*double_batch([row]))
        dscene, _ = double.encode_scene(*[double_batch([row])[i] for i in (0,1,3,5)])
        g, opponents, candidates, spatial = [lua.eval(native.lua(row[name])) for name in ('global','opponents','candidates','spatial')]
        memory = memories.setdefault(sequence_key(row), lua.table())
        scores, v, _ = network.forward(weights, g, opponents, candidates, spatial, memory, row['turn'])
        lscene, _, _ = relational.scene(weights, g, opponents, spatial)
        errors = [abs(logits[0,i].item() - scores[i+1]) for i in range(len(row['candidates']))]
        derrors = [abs(dlogits[0,i].item() - scores[i+1]) for i in range(len(row['candidates']))]
        results.append(dict(turn=row['turn'], candidates=len(errors), float32_logit=max(errors),
                            float64_logit=max(derrors), float32_value=abs(value.item()-v),
                            float64_value=abs(dvalue.item()-v),
                            float32_scene=max(abs(scene[0,i].item()-lscene[i+1]) for i in range(scene.shape[1])),
                            float64_scene=max(abs(dscene[0,i].item()-lscene[i+1]) for i in range(dscene.shape[1])),
                            python_choice=logits.argmax(1).item(), lua_choice=max(range(len(errors)),key=lambda i:scores[i+1])))
        if row.get('committed',True) and memory.turn != row['turn']:
            write = row.get('memory_write', row)
            _, _, pending = network.forward(weights, lua.eval(native.lua(write['global'])), lua.eval(native.lua(write['opponents'])),
                                             lua.table(), lua.eval(native.lua(write['spatial'])), memory, row['turn'])
            relational.commit(memory, pending)
network_module.batch = original_batch
print(json.dumps(dict(version=state['runner']['version'], diagnosis_only=True, rows=results), indent=2), flush=True)
