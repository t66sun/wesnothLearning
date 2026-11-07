set -eu
task_root=/home/tongshu/myDev/wesnothLearning/verification/teacher_search_20261107
test -f "$task_root/experiment_v2/final.json"
test -f "$task_root/export/metadata/SHA256SUMS.json"
test ! -e "$task_root/export/raw_evidence.tar.gz"
test ! -e "$task_root/export/metadata.tar.gz"
tar -I 'gzip -1' -cf "$task_root/export/raw_evidence.tar.gz" --exclude=./sources --exclude=./export -C "$task_root" .
tar -I 'gzip -1' -cf "$task_root/export/metadata.tar.gz" -C "$task_root/export/metadata" .
/home/tongshu/venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
root=Path('/home/tongshu/myDev/wesnothLearning/verification/teacher_search_20261107/export')
rows={}
for name in ('raw_evidence.tar.gz','metadata.tar.gz'):
 path=root/name
 with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
 rows[name]=dict(bytes=path.stat().st_size,sha256=digest)
with (root/'ARCHIVES.json').open('x') as stream:json.dump(rows,stream,indent=2);stream.write('\n')
print(json.dumps(rows))
PY
