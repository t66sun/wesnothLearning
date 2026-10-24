import ast,difflib
from pathlib import Path
old=Path('/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022')
new=Path.cwd()
for p in ['learning/model.py','learning/train.py','learning/features.py','learning/experiment.py','learning/lite_host.py','learning/manifest.py','lua/candidates.lua','lua/spatial.lua','engine_lite/lua/host.lua','learning/sequences.py','learning/data.py']:
 a=(old/p).read_text();b=(new/p).read_text()
 print('\nFILE',p,'text_equal',a==b)
 if p.endswith('.py'):
  print('AST_EQUAL',ast.dump(ast.parse(a))==ast.dump(ast.parse(b)))
 if a!=b:
  diff=list(difflib.unified_diff(a.splitlines(),b.splitlines(),n=2))
  print('\n'.join(diff[:260]));print('DIFF_LINES',len(diff))
