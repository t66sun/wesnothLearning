import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
identities={};mismatches=[]
for group in ('learning','lua'):
    for name,expected in manifest['source'][group].items():
        if not name.endswith(('.py','.lua','.json')):continue
        path=Path(group)/name
        actual=hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest()
        if actual!=expected:mismatches.append(str(path))
assert not mismatches,mismatches
for fmt in ('duel','ffa4','team2v2'):
    path=root/(fmt+'_selected.pt');digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest==summary['formats'][fmt]['checkpoint_sha256']
    identities[fmt]=dict(bytes=path.stat().st_size,sha256=digest,selected_version=summary['formats'][fmt]['version'])
print(json.dumps(dict(source_identity='all frozen Python/Lua/JSON sources match after LF normalization',checkpoints=identities),indent=2))
