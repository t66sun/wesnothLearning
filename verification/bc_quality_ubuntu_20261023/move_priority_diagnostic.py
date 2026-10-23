import collections,json
from learning.common import ROOT,write_json
from learning.features import ACTION
from learning.sequences import read_shards
out=ROOT/'verification/bc_quality_ubuntu_20261023';ix={n:i for i,(n,s) in enumerate(ACTION)}
report={}
for part in ('train','validation'):
 rows=read_shards(sorted((out/'data/ffa4').glob('*.jsonl.gz')),partition=part,limit=2048,seed=71,format_name='ffa4');c=collections.Counter()
 for r in rows:
  t=r['candidates'][r['choice']]
  moves=[(i,a) for i,a in enumerate(r['candidates']) if a['kind']=='move' and a.get('full')]
  if not moves:continue
  def priority(pair):
   a=pair[1];return float(a['features'][ix['move_gain']])*25+float(a['features'][ix['own_leader']])*8
  p,a=max(moves,key=priority)
  if t['kind']=='move':
   c['moves']+=1;c['rank_correct']+=p==r['choice'];c['chosen_gain_positive']+=float(t['features'][ix['move_gain']])*25>.05
  elif t['kind']=='end_turn':
   c['end_turn_with_moves']+=1;c['end_turn_positive_gain']+=float(a['features'][ix['move_gain']])*25>.05
 report[part]=dict(c)
write_json(out/'move_priority_diagnostic.json',report);print(json.dumps(report),flush=True)
