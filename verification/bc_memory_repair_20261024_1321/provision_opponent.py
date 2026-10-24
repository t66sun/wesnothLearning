from pathlib import Path
import hashlib
root=Path.cwd()
assert root.name=='validation_memory_repair_20261024_1321'
source=Path('/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022/runs/v5_lite18h_20261024_003512/frozen/opponents')
(root/'data/opponents').symlink_to(source,target_is_directory=True)
print('ASTRA_SHA256',hashlib.sha256((source/'gpt6astra.zip').read_bytes()).hexdigest())
