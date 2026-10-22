import json
import random
import tempfile
import unittest
from pathlib import Path
import torch
from lupa import LuaRuntime
from learning.common import ROOT
from learning.model import Policy, batch
from learning.features import GLOBAL,OPPONENT,ACTION,VERSION,schema,ENTITY,GEOMETRY,SPATIAL_CHANNELS,UNIT_TYPES
from learning.rewards import RewardConfig
from tests.test_lua_contracts import initialize
from learning.formats import FORMATS,PLAYERS
from learning.export import lua_parameters, compact_lua, export, export_checkpoints, load_model
from learning.data import advantages, reward, split, write_shard, read_shards
from learning.train import train, checkpoint, restore_rng
import addons
import native


def _spatial():
    return dict(entities=[],board=[[[0.0]*16 for _ in range(16)] for _ in SPATIAL_CHANNELS])

def record(players=2, game='g', index=0):
    rng=random.Random(index+players)
    return dict(schema=VERSION,global_ignored=0,**{'global':[rng.uniform(-1,1) for _ in GLOBAL]},
        opponents=[[rng.random() for _ in OPPONENT] for _ in range(players-1)],
        candidates=[dict(kind='end_turn',features=[rng.uniform(-1,1) for _ in ACTION[:-1]]+[0],
                         geometry=[0.0]*len(GEOMETRY),local=[0.0]*(19*len(SPATIAL_CHANNELS)))
                    for _ in range(8)],
        spatial=_spatial(),architecture_id='relational_v5',engine_id='lite-0.1',
        rules_version='fixture',rng_version='fixture',candidate_version='candidates-v1',
        reward_version=0,reward_formula_id=RewardConfig().reward_formula_id,
        reward_config=RewardConfig().to_dict(),
        reward_raw=dict(economy=0.,control=0.,explored=0.),
        choice=1,log_probability=-2.0794415,value=.2,version='v1',side=1,turn=index,
        game_id=game,game_family=game,split='train',reward=1.,value_valid=True,players=players,teacher='gpt6astra',source='astra',format='duel')


class CoreTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.manual_seed(19);random.seed(19)

    def test_lua_numeric_and_ties(self):
        lua,modules=initialize();network=modules['network.lua']
        worst=0.
        for fmt in FORMATS:
            model=Policy(fmt).eval();weights=lua.eval(compact_lua(lua_parameters(model)))
            players=PLAYERS[fmt]
            r=record(players)
            r['candidates']*=16
            logits,value=model(*batch([r]))
            scores,v,_=network.forward(weights,lua.eval(native.lua(r['global'])),lua.eval(native.lua(r['opponents'])),lua.eval(native.lua(r['candidates'])),lua.eval(native.lua(r['spatial'])),lua.table(),r['turn'])
            err=max(abs(logits[0,i].item()-scores[i+1]) for i in range(128))
            worst=max(worst,err,abs(value.item()-v))
            self.assertLessEqual(worst,1e-5)
            if torch.topk(logits[0],2).values.diff().abs().item()>2e-5:
                self.assertEqual(network.choose(scores,False)[0]-1,logits.argmax().item())
        self.assertEqual(network.choose(lua.eval('{1,1,1}'),False)[0],1)
        self.assertEqual(network.choose(lua.eval('{1,1+1e-8,1}'),False)[0],2)
        print('Python/Lua maximum absolute error:',worst)

    def test_opponent_permutation_and_padding(self):
        model=Policy('duel').eval();r=record(8)
        a=model(*batch([r]))[0]
        r['opponents'].reverse()
        b=model(*batch([r]))[0]
        self.assertTrue(torch.allclose(a,b,atol=1e-6))
        r2=record(2)
        self.assertTrue(torch.allclose(model(*batch([r2]))[0][0],model(*batch([r,r2]))[0][1],atol=1e-6))

    def test_capacity_and_cuda_defaults(self):
        from learning.experiment import default_config
        from learning.__main__ import parser
        model=Policy('duel')
        # Only the unit embedding grows when the frozen vocabulary expands.
        self.assertEqual(sum(p.numel() for p in model.parameters()),763122+16*len(UNIT_TYPES))
        self.assertEqual(model.unit_embedding.embedding_dim,16)
        self.assertEqual(model.unit_embedding.num_embeddings,len(UNIT_TYPES))
        self.assertEqual([l.out_features for l in model.scorer if isinstance(l,torch.nn.Linear)],[512,256,128,1])
        self.assertEqual(model.opponent[0].out_features,16)
        self.assertEqual(model.value[0].out_features,128)
        self.assertEqual(default_config()['device'],'cuda')
        self.assertEqual(parser().parse_args(['run']).device,'cpu')

    def test_reward_and_gae(self):
        result=dict(bots=['a','b'],winner=0,rank_points={1:.5,2:.5})
        self.assertEqual(reward(result,1),0.)
        result=dict(bots=['a','b','c','d'],rank_points={1:3.,2:2.,3:1.,4:0.})
        self.assertEqual(reward(result,1),1.);self.assertEqual(reward(result,4),-1.)
        result=dict(bots=['a','b'],winner=1);self.assertEqual(reward(result,1),1)
        rows=[record(index=i) for i in range(2)]
        adv,ret=advantages(rows)
        self.assertAlmostEqual(adv[-1],.8)
        self.assertAlmostEqual(ret[-1],1.)
        self.assertGreater(adv[0],0.)

    def test_game_split_and_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'game.jsonl.gz'
            write_shard(p,'same-game',[record(),record()],dict(bots=['a','b'],winner=1,faults={}))
            rows=read_shards([p]);self.assertEqual(len(rows),2)
            self.assertEqual({r['split'] for r in rows},{split('same-game')})

    def test_training_and_resume(self):
        model=Policy('duel');optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
        rows=[record(index=i) for i in range(5)]
        before=model.scorer[0].weight.detach().clone()
        self.assertGreater(train(model,optimizer,rows,'bc',epochs=1,minibatch=4)['updates'],0)
        self.assertFalse(torch.equal(before,model.scorer[0].weight))
        with torch.no_grad():
            for r in rows:
                logits,value=model(*batch([r]));r['value']=value.item()
                r['log_probability']=torch.log_softmax(logits[0],0)[r['choice']].item()
        ppo=[dict(r,teacher=False,source='policy') for r in rows]
        self.assertGreater(train(model,optimizer,ppo,'ppo',epochs=1,minibatch=4,bc_records=rows)['updates'],0)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'latest.pt';checkpoint(p,model,optimizer,deadline=1234,data_position=5)
            expected=torch.rand(4);model2,state=load_model(p,'duel');restore_rng(state)
            self.assertTrue(torch.equal(expected,torch.rand(4)))
            self.assertEqual(state['deadline'],1234)
            opt2=torch.optim.Adam(model2.parameters());opt2.load_state_dict(state['optimizer'])
            self.assertTrue(opt2.state_dict()['state'])

    def test_sdk_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoints={}
            for fmt in FORMATS:
                model=Policy(fmt);p=Path(tmp)/(fmt+'.pt');checkpoint(p,model,torch.optim.Adam(model.parameters()),metrics={'updates':1})
                checkpoints[fmt]=p
            audit={}
            for fmt in FORMATS:
                audit[fmt]=[record(players=PLAYERS[fmt],index=0),record(players=PLAYERS[fmt],index=1)]
                for row in audit[fmt]:
                    row['format']=fmt;row['candidates']*=16
            old_limit=addons.MAX_PACKAGE_BYTES
            addons.MAX_PACKAGE_BYTES=64*1024*1024
            try:
                export_checkpoints(checkpoints,tmp,audit_records=audit)
                manifest=json.loads(Path(tmp,'export.json').read_text())
                self.assertEqual(set(manifest['models']),set(FORMATS))
                for m in manifest['models'].values(): self.assertLessEqual(m['python_lua_max_error'],1e-5)
                with addons.open_addon(Path(tmp)/'NeuralArena.zip') as addon:
                    self.assertEqual(addons.validate(addon),'NeuralArena')
                    self.assertNotIn('@ADDON@',(addon/'lua/bot.lua').read_text())
                    for fmt in FORMATS: self.assertTrue((addon/'lua'/f'weights_{fmt}.lua').exists())
            finally:
                addons.MAX_PACKAGE_BYTES=old_limit

    def test_old_shared_checkpoint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'old.pt';torch.save(dict(features=schema()|dict(version=2)),p)
            with self.assertRaises(ValueError): load_model(p,'duel')

    def test_minibatch_resume_matches_uninterrupted_training(self):
        import copy
        rows=[record(index=i) for i in range(3)]
        def new():
            torch.manual_seed(31);random.seed(31)
            m=Policy('duel');return m,torch.optim.Adam(m.parameters(),lr=3e-4)
        full,opt=new();expected=train(full,opt,rows,'bc',epochs=2,minibatch=8)
        partial,opt2=new();saved={}
        class Interrupted(Exception): pass
        def stop(cursor):
            if cursor['updates']==2:
                saved.update(model=copy.deepcopy(partial.state_dict()),optimizer=copy.deepcopy(opt2.state_dict()),
                    python_rng=random.getstate(),torch_rng=torch.get_rng_state(),cursor=cursor)
                raise Interrupted()
        with self.assertRaises(Interrupted): train(partial,opt2,rows,'bc',epochs=2,minibatch=8,on_step=stop)
        resumed=Policy('duel');resumed.load_state_dict(saved['model'])
        opt3=torch.optim.Adam(resumed.parameters(),lr=3e-4);opt3.load_state_dict(saved['optimizer'])
        random.setstate(saved['python_rng']);torch.set_rng_state(saved['torch_rng'])
        actual=train(resumed,opt3,rows,'bc',epochs=2,minibatch=8,progress=saved['cursor'])
        self.assertEqual(actual,expected)
        for name,value in full.state_dict().items(): self.assertTrue(torch.equal(value,resumed.state_dict()[name]),name)


if __name__=='__main__': unittest.main()
