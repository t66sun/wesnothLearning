"""Compare two initial public views on a fixed board using the official filtered rules."""
from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path

import _engine_lite
from learning.common import sha256
from learning.features import schema
from learning.lite_host import host_modules


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    parser=ArgumentParser(description=__doc__);parser.add_argument('rules',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();text=args.rules.read_text();rules=json.loads(text)
    tile=['Gg']*49
    for p in (6,17):tile[p]='Wo'
    def unit(name,kind,side,pos,leader):
        definition=rules['units'][kind]
        return dict(id=name,unit_type=kind,side=side,pos=pos,leader=leader,hp=definition['hp'],
                    moves=definition['moves'],attacks_left=1,xp=0,status=[],traits=[],acted=False)
    modules=host_modules()
    src=modules['candidates.lua']
    # Preserve normal candidate generation, then request exactly the same legal
    # hypothetical strike through the teacher-facing wesnoth.simulate_combat API.
    modules['candidates.lua']='local M=(function()\n'+src+'''\nend)()
        local generate=M.generate
        function M.generate(obs)
            local actions,timing=generate(obs)
            local a=assert(wesnoth.units.get(2,4)):clone();local d=assert(wesnoth.units.get(4,4))
            a.x,a.y=3,4
            local ar,dr=wesnoth.simulate_combat(a,1,d)
            local function stats(v)
                local hp={};for k,p in pairs(v.hp_chance) do hp[tostring(k)]=p end
                return {average_hp=v.average_hp,hp_chance=hp,poisoned=v.poisoned,slowed=v.slowed}
            end
            timing.counterexample={attacker=stats(ar),defender=stats(dr)}
            return actions,timing
        end
        return M
    '''
    twins=[];candidates=[]
    for donor_pos in (17,6):
        board=dict(width=7,height=7,terrain=tile,seed=20261104,max_turns=5,allow_approximate=True,
            sides=[dict(id=s,team=str(s),gold=0,recruit=[],fog=False,shroud=False,share_view=False,share_maps=False) for s in (1,2)],
            units=[unit('actor','Spearman',1,22,True),unit('defender','Skeleton',2,24,True),unit('donor','Death Knight',2,donor_pos,False)])
        e=_engine_lite.LiteEngine(text,json.dumps(board));e.configure_host(json.dumps(modules))
        before=json.loads(e.snapshot())['game'];view=json.loads(e.observe(1));legal=json.loads(e.legal_actions(1))
        assert [u['id'] for u in view['units']]==['actor','defender']
        assert any(a['kind']=='move' and a['unit']=='actor' and a['to']==23 for a in legal)
        row=json.loads(e.decision(1));assert before==json.loads(e.snapshot())['game']
        twins.append(dict(board=board,public_view=view,public_legal_actions=legal,public_view_sha256=digest(view),
            legal_sha256=digest(legal),scene_sha256=digest([row['global'],row['opponents'],row['spatial']]),
            candidates_sha256=digest(row['candidates']),forecast=row['timing']['counterexample']))
        candidates.append(row['candidates'])
    left,right=twins
    assert left['public_view']==right['public_view'] and left['public_legal_actions']==right['public_legal_actions']
    different=[]
    fields=[f[0] for f in schema()['action_features']]
    for a,b in zip(*candidates):
        if a!=b:
            different.append(dict(action={k:a[k] for k in ('kind','x','y','tx','ty','ex','ey','weapon') if k in a},
                features={name:[x,y] for name,x,y in zip(fields,a['features'],b['features']) if x!=y}))
    out=dict(rules_sha256=sha256(args.rules),extension_sha256=sha256(_engine_lite.__file__),twins=twins,
             forecast_equal=left['forecast']==right['forecast'],candidate_counts=list(map(len,candidates)),candidate_differences=different)
    args.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(public_equal=True,legal_equal=True,forecast_equal=out['forecast_equal'],
        attacker_average_hp=[v['forecast']['attacker']['average_hp'] for v in twins],
        defender_average_hp=[v['forecast']['defender']['average_hp'] for v in twins],
        candidates_equal=left['candidates_sha256']==right['candidates_sha256'],different_candidates=len(different))),flush=True)


if __name__=='__main__':main()
