"""Export the exact tested source text for a local equivalence check."""
from learning.common import ROOT,read_json,write_json
out=ROOT/'verification/bc_quality_ubuntu_20261023'
identity=read_json(out/'identity.json')
names={**identity['source_hashes'],**identity['training_source_hashes']}
write_json(out/'source_snapshot.json',{name:(ROOT/name).read_text(encoding='utf-8-sig') for name in names})
print('SOURCE_SNAPSHOT',len(names),flush=True)
