"""Schema 4 policy; every operation has a pure Lua deployment counterpart."""
import torch
import numpy as np
from torch import nn
from .features import GLOBAL, OPPONENT, ACTION, UNIT_TYPES, ENTITY, GEOMETRY, SPATIAL_CHANNELS
from .formats import FORMATS

ARCHITECTURE = dict(id='relational_v5', unit_embedding=16, entity_hidden=64, entity_layers=2,
    heads=4, ffn=128, spatial_size=16, spatial_channels=len(SPATIAL_CHANNELS), conv_channels=16,
    local_hexes=19, local_hidden=32, gru=128, memory_slots=32, memory_hidden=64,
    scorer_hidden=[512,256,128], value_hidden=128, replay_turns=8)


class EntityBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.q=nn.Linear(64,64); self.k=nn.Linear(64,64); self.v=nn.Linear(64,64)
        self.out=nn.Linear(64,64); self.ff1=nn.Linear(64,128); self.ff2=nn.Linear(128,64)

    def forward(self,x,mask):
        b,n,_=x.shape
        q,k,v=[layer(x).view(b,n,4,16).transpose(1,2) for layer in (self.q,self.k,self.v)]
        scores=((q@k.transpose(-1,-2))/4).masked_fill(~mask[:,None,None,:],-1e30)
        y=(scores.softmax(-1)@v).transpose(1,2).reshape(b,n,64)
        x=torch.relu(x+self.out(y))
        return torch.relu(x+self.ff2(torch.relu(self.ff1(x))))*mask[...,None]


class Policy(nn.Module):
    def __init__(self,format_name):
        super().__init__()
        if format_name not in FORMATS: raise ValueError('an explicit supported format is required')
        self.format_name=format_name
        self.unit_embedding=nn.Embedding(len(UNIT_TYPES),16)
        self.entity=nn.Linear(len(ENTITY)+16,64)
        self.entities=nn.ModuleList([EntityBlock(),EntityBlock()])
        self.opponent=nn.Sequential(nn.Linear(len(OPPONENT),16),nn.ReLU())
        self.conv1=nn.Conv2d(len(SPATIAL_CHANNELS),16,3,padding=1)
        self.conv2=nn.Conv2d(16,16,3,padding=1)
        self.local=nn.Linear(19*len(SPATIAL_CHANNELS),32)
        self.scene_width=len(GLOBAL)+32+64+16
        self.gru=nn.GRUCell(self.scene_width,128)
        self.summary=nn.Linear(self.scene_width,64)
        self.memory_query=nn.Linear(128,64); self.memory_key=nn.Linear(65,64); self.memory_value=nn.Linear(65,64)
        context=self.scene_width+128+64
        self.scorer=nn.Sequential(nn.Linear(context+len(ACTION)-1+16+128+32+len(GEOMETRY),512),nn.ReLU(),
            nn.Linear(512,256),nn.ReLU(),nn.Linear(256,128),nn.ReLU(),nn.Linear(128,1))
        self.value=nn.Sequential(nn.Linear(context,128),nn.ReLU(),nn.Linear(128,1))

    def encode_scene(self,g,opponents,om,p):
        e=self.opponent(opponents)
        mean=(e*om[...,None]).sum(1)/om.sum(1,keepdim=True).clamp(min=1)
        maximum=e.masked_fill(~om[...,None],-1e30).amax(1)
        maximum=torch.where(om.any(1,keepdim=True),maximum,torch.zeros_like(maximum))
        entities=torch.relu(self.entity(torch.cat([p['entities'],self.unit_embedding(p['types'])],-1)))
        for layer in self.entities: entities=layer(entities,p['entity_mask'])
        pool=(entities*p['entity_mask'][...,None]).sum(1)/p['entity_mask'].sum(1,keepdim=True).clamp(min=1)
        board=torch.relu(self.conv2(torch.relu(self.conv1(p['board'])))).mean((-1,-2))
        return torch.cat([g,mean,maximum,pool,board],-1),entities

    def memory_read(self,h,slots,ages):
        if not slots: return h.new_zeros(1,64)
        values=torch.stack(slots,1)
        age=h.new_tensor(ages).view(1,-1,1)/30
        values=torch.cat([values,age],-1)
        scores=(self.memory_key(values)*self.memory_query(h)[:,None]).sum(-1)/8
        return (scores.softmax(-1)[...,None]*self.memory_value(values)).sum(1)

    def context(self,scene,histories,current_turns):
        # Raw history rows are shared by attach_histories within each sequence.
        # All caches live in this call: every optimizer update uses current weights.
        rows={}; active=set(); nodes=[None]; edges={}; paths=[]
        for history in histories:
            parent=0; path=[]
            for j,row in enumerate(history):
                identity=id(row); rows[identity]=row
                if j>=len(history)-ARCHITECTURE['replay_turns']: active.add(identity)
                edge=(parent,identity)
                if edge not in edges:
                    edges[edge]=len(nodes);nodes.append(edge)
                parent=edges[edge];path.append(parent)
            paths.append(path)
        encoded={}; summaries={}
        for differentiable in (False,True):
            selected=[key for key in rows if (key in active)==differentiable]
            with torch.set_grad_enabled(torch.is_grad_enabled() and differentiable):
                for start in range(0,len(selected),32):
                    keys=selected[start:start+32]
                    tensors=batch([rows[key] for key in keys],scene.device,include_history=False)
                    s,_=self.encode_scene(tensors[0],tensors[1],tensors[3],tensors[5])
                    summary=torch.tanh(self.summary(s))
                    for j,key in enumerate(keys):
                        encoded[key]=s[j:j+1];summaries[key]=summary[j:j+1]
        zero=scene.new_zeros(1,128); prefix={0:zero}; replay={}
        needed=set()
        for path in paths:
            cut=max(0,len(path)-ARCHITECTURE['replay_turns'])
            needed.update(path[:cut] if torch.is_grad_enabled() else path)
        with torch.no_grad():
            for node,(parent,key) in enumerate(nodes[1:],1):
                if node in needed: prefix[node]=self.gru(encoded[key],prefix[parent])
        output=[]
        for i,(history,path) in enumerate(zip(histories,paths)):
            cut=max(0,len(path)-ARCHITECTURE['replay_turns'])
            boundary=path[cut-1] if cut else 0
            h=prefix[boundary]
            if torch.is_grad_enabled():
                for node in path[cut:]:
                    cache_key=(boundary,node)
                    if cache_key not in replay: replay[cache_key]=self.gru(encoded[nodes[node][1]],h)
                    h=replay[cache_key]
            elif path:
                h=prefix[path[-1]]
            slots=[];turns=[]
            for j in range(max(0,len(history)-ARCHITECTURE['memory_slots']),len(history)):
                value=summaries[id(history[j])]
                slots.append(value.detach() if j<cut else value);turns.append(history[j]['turn'])
            read=self.memory_read(h,slots,[current_turns[i]-t for t in turns])
            output.append(torch.cat([scene[i:i+1],h,read],-1))
        return torch.cat(output)

    def forward(self,global_features,opponents,actions,opponent_mask,action_mask,payload):
        scene,entities=self.encode_scene(global_features,opponents,opponent_mask,payload)
        context=(torch.cat([scene,payload['memory_context']],-1) if 'memory_context' in payload
                 else self.context(scene,payload['histories'],payload['turns']))
        def gather(name):
            direct=torch.relu(self.entity(torch.cat([payload[name],self.unit_embedding(payload[name+'_types'])],-1)))
            indices=payload[name+'_indices']
            attended=entities.gather(1,indices.clamp(min=0)[...,None].expand(-1,-1,64))
            return torch.where((indices>=0)[...,None],attended,direct)*payload[name+'_present'][...,None]
        inputs=torch.cat([context[:,None].expand(-1,actions.shape[1],-1),actions[...,:-1],
            self.unit_embedding(actions[...,-1].long()),gather('actors'),gather('targets'),
            torch.relu(self.local(payload['local'])),payload['geometry']],-1)
        logits=self.scorer(inputs).squeeze(-1).masked_fill(~action_mask,-torch.inf)
        return logits,self.value(context).squeeze(-1)


def batch(records,device='cpu',include_history=True):
    b=len(records); n=max(1,max(len(r['opponents']) for r in records)); a=max(1,max(len(r['candidates']) for r in records))
    zeros=lambda shape: np.zeros(shape,dtype=np.float32)
    stack=lambda values: np.stack(values).astype(np.float32,copy=False)
    g=stack([r['global'] for r in records])
    opponents=zeros((b,n,len(OPPONENT))); actions=zeros((b,a,len(ACTION)))
    om=np.zeros((b,n),dtype=bool); am=np.zeros((b,a),dtype=bool)
    p=dict(entities=zeros((b,128,len(ENTITY))),types=np.zeros((b,128),dtype=np.int64),
        entity_mask=np.zeros((b,128),dtype=bool),board=stack([r['spatial']['board'] for r in records]),
        local=zeros((b,a,19*len(SPATIAL_CHANNELS))),geometry=zeros((b,a,len(GEOMETRY))))
    for name in ('actors','targets'):
        p[name]=zeros((b,a,len(ENTITY))); p[name+'_types']=np.zeros((b,a),dtype=np.int64)
        p[name+'_indices']=np.full((b,a),-1,dtype=np.int64); p[name+'_present']=zeros((b,a))
    for i,r in enumerate(records):
        if len(r['opponents']): opponents[i,:len(r['opponents'])]=r['opponents']; om[i,:len(r['opponents'])]=True
        es=r['spatial']['entities']; lookup={e['id']:j for j,e in enumerate(es)}
        if es:
            p['entities'][i,:len(es)]=stack([e['features'] for e in es])
            p['types'][i,:len(es)]=[e['type_index'] for e in es];p['entity_mask'][i,:len(es)]=True
        candidates=r['candidates'];count=len(candidates)
        if count:
            actions[i,:count]=stack([c['features'] for c in candidates]);am[i,:count]=True
            p['local'][i,:count]=stack([c['local'] for c in candidates])
            p['geometry'][i,:count]=stack([c['geometry'] for c in candidates])
        for j,c in enumerate(r['candidates']):
            for name,key in (('actors','actor'),('targets','target')):
                if c.get(key):
                    e=c[key]; p[name][i,j]=e['features']; p[name+'_types'][i,j]=e['type_index']
                    p[name+'_indices'][i,j]=lookup.get(e['id'],-1); p[name+'_present'][i,j]=1
    tensor=lambda value: torch.as_tensor(value,device=device)
    p={key:tensor(value) for key,value in p.items()}
    p.update(histories=[r.get('_history',[]) if include_history else [] for r in records],turns=[r['turn'] for r in records])
    return tensor(g),tensor(opponents),tensor(actions),tensor(om),tensor(am),p
