"""Pin a small set of upstream references; source copies stay outside the package."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

repositories={
    'HumanCompatibleAI/imitation':['src/imitation/algorithms/bc.py','src/imitation/algorithms/base.py','LICENSE'],
    'ARISE-Initiative/robomimic':['robomimic/utils/dataset.py','LICENSE'],
    'DLR-RM/stable-baselines3':['stable_baselines3/common/callbacks.py','LICENSE'],
    'pytorch/rl':['tutorials/sphinx-tutorials/rb_tutorial.py','LICENSE'],
}
root=Path('data/references/github_refactor_20261024')
def get(url):
    request=urllib.request.Request(url,headers={'User-Agent':'WesnothLearning-source-research'})
    with urllib.request.urlopen(request,timeout=30) as response:return response.read()
def fetch(item):
    repository,paths=item
    commit=json.loads(get(f'https://api.github.com/repos/{repository}/commits/HEAD'))['sha']
    result=dict(repository=repository,commit=commit,files=[])
    for relative in paths:
        raw=get(f'https://raw.githubusercontent.com/{repository}/{commit}/{relative}')
        destination=root/repository/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():raise FileExistsError(destination)
        destination.write_bytes(raw)
        result['files'].append(dict(path=relative,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),url=f'https://github.com/{repository}/blob/{commit}/{relative}'))
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    entries=list(pool.map(fetch,repositories.items()))
output=Path(__file__).parent/'sources.json'
output.write_text(json.dumps(dict(retrieved='2026-10-24',sources=entries),indent=2)+'\n',encoding='utf-8')
for entry in entries:print(entry['repository'],entry['commit'],len(entry['files']))
