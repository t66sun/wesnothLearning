"""Allow recorded Windows/Ubuntu line-ending differences, never code changes."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
identities={};mismatches=[];endings=[]
for group in ('learning','lua'):
    for name,expected in manifest['source'][group].items():
        if not name.endswith(('.py','.lua','.json')):continue
        path=Path(group)/name;raw=path.read_bytes();lf=raw.replace(b'\r\n',b'\n')
        variants=(raw,lf,lf.replace(b'\n',b'\r\n'))
        if not any(hashlib.sha256(value).hexdigest()==expected for value in variants):mismatches.append(str(path))
        elif hashlib.sha256(raw).hexdigest()!=expected:endings.append(str(path))
assert not mismatches,mismatches
for fmt in ('duel','ffa4','team2v2'):
    path=root/(fmt+'_selected.pt');digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest==summary['formats'][fmt]['checkpoint_sha256']
    identities[fmt]=dict(bytes=path.stat().st_size,sha256=digest,selected_version=summary['formats'][fmt]['version'])
print(json.dumps(dict(source_identity='all frozen Python/Lua/JSON sources match, allowing only LF/CRLF conversion',line_ending_only=endings,checkpoints=identities),indent=2))
