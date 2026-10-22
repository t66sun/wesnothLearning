-- Deployment implementation of relational_v5. Lua numbers accumulate exported float32 weights.
local M={}
local function zeros(n) local a={};for i=1,n do a[i]=0 end;return a end
local function append(a,b) for _,v in ipairs(b) do a[#a+1]=v end end
local function linear(x,l,relu)
    local y={};for i,row in ipairs(l.weight) do local v=l.bias[i];for j,t in ipairs(x) do v=v+row[j]*t end;y[i]=relu and math.max(0,v) or v end;return y
end
local function softmax(x)
    local m=-math.huge;for _,v in ipairs(x) do m=math.max(m,v) end
    local y,s={},0;for i,v in ipairs(x) do y[i]=math.exp(v-m);s=s+y[i] end
    for i,v in ipairs(y) do y[i]=v/s end;return y
end
local function mlp(x,layers) for i,l in ipairs(layers) do x=linear(x,l,i<#layers) end;return x end
local function project(w,e)
    local x={};append(x,e.features);append(x,w.unit_embedding[e.type_index+1]);return linear(x,w.entity,true)
end
local function conv(x,l)
    local y={}
    for o,channels in ipairs(l.weight) do
        y[o]={};for r=1,16 do y[o][r]={};for c=1,16 do
            local v=l.bias[o]
            for k,kernel in ipairs(channels) do for dy=1,3 do for dx=1,3 do
                local row=x[k][r+dy-2];if row and row[c+dx-2] then v=v+kernel[dy][dx]*row[c+dx-2] end
            end end end
            y[o][r][c]=math.max(0,v)
        end end
    end
    return y
end
function M.scene(w,g,opponents,spatial)
    local mean,maximum=zeros(16),zeros(16)
    for _,o in ipairs(opponents) do local e=linear(o,w.opponent[1],true)
        for j,v in ipairs(e) do mean[j]=mean[j]+v/#opponents;maximum[j]=math.max(maximum[j],v) end
    end
    local entities,lookup={},{}
    for i,e in ipairs(spatial.entities) do entities[i]=project(w,e);lookup[e.id]=i end
    for _,l in ipairs(w.entities) do
        local qs,ks,vs={},{},{}
        for i,x in ipairs(entities) do qs[i]=linear(x,l.q);ks[i]=linear(x,l.k);vs[i]=linear(x,l.v) end
        local output={}
        for i,x in ipairs(entities) do
            local attended=zeros(64)
            for head=0,3 do
                local scores={};for j,k in ipairs(ks) do local s=0;for d=1,16 do local z=head*16+d;s=s+qs[i][z]*k[z] end;scores[j]=s/4 end
                local probabilities=softmax(scores)
                for j,p in ipairs(probabilities) do for d=1,16 do local z=head*16+d;attended[z]=attended[z]+p*vs[j][z] end end
            end
            local projected=linear(attended,l.out);local residual={}
            for j,v in ipairs(x) do residual[j]=math.max(0,v+projected[j]) end
            local ff=linear(linear(residual,l.ff1,true),l.ff2)
            output[i]={};for j,v in ipairs(residual) do output[i][j]=math.max(0,v+ff[j]) end
        end
        entities=output
    end
    local pool=zeros(64)
    for _,e in ipairs(entities) do for j,v in ipairs(e) do pool[j]=pool[j]+v/#entities end end
    local board=conv(conv(spatial.board,w.conv1),w.conv2);local grid=zeros(16)
    for i,rows in ipairs(board) do for _,row in ipairs(rows) do for _,v in ipairs(row) do grid[i]=grid[i]+v/256 end end end
    local scene={};append(scene,g);append(scene,mean);append(scene,maximum);append(scene,pool);append(scene,grid)
    return scene,entities,lookup
end
local function sigmoid(v) if v>=0 then return 1/(1+math.exp(-v)) else local e=math.exp(v);return e/(1+e) end end
local function tanh(v) return 2*sigmoid(2*v)-1 end
local function gru(w,x,h)
    local i=linear(x,{weight=w.weight_ih,bias=w.bias_ih});local v=linear(h,{weight=w.weight_hh,bias=w.bias_hh});local out={}
    for j=1,128 do
        local r=sigmoid(i[j]+v[j]);local z=sigmoid(i[128+j]+v[128+j]);local n=tanh(i[256+j]+r*v[256+j])
        out[j]=(1-z)*n+z*h[j]
    end
    return out
end
function M.forward(w,g,opponents,candidates,spatial,memory,turn)
    assert(w.architecture_id=='relational_v5','incompatible network')
    local scene,entities,lookup=M.scene(w,g,opponents,spatial)
    local h=memory.hidden or zeros(128);local slots=memory.slots or {};local scores={}
    local context={};append(context,scene);append(context,h)
    local read=zeros(64)
    if #slots>0 then
        local query=linear(h,w.memory_query);local keys,values={},{}
        for i,s in ipairs(slots) do
            local row={};append(row,s.value);row[#row+1]=(turn-s.turn)/30
            local key=linear(row,w.memory_key);values[i]=linear(row,w.memory_value);local dot=0
            for j,v in ipairs(query) do dot=dot+v*key[j] end;keys[i]=dot/8
        end
        for i,p in ipairs(softmax(keys)) do for j,v in ipairs(values[i]) do read[j]=read[j]+p*v end end
    end
    append(context,read)
    for i,a in ipairs(candidates) do
        local row={};append(row,context)
        for j=1,#a.features-1 do row[#row+1]=a.features[j] end
        append(row,w.unit_embedding[a.features[#a.features]+1])
        for _,name in ipairs {'actor','target'} do
            local e=a[name];append(row,e and (lookup[e.id] and entities[lookup[e.id]] or project(w,e)) or zeros(64))
        end
        append(row,linear(a['local'],w['local'],true));append(row,a.geometry)
        scores[i]=mlp(row,w.scorer)[1]
    end
    -- Reading is pure. Only a successful execution commits this proposed turn write.
    local pending
    if memory.turn~=turn then
        local summary=linear(scene,w.summary);for i,v in ipairs(summary) do summary[i]=tanh(v) end
        pending={turn=turn,hidden=gru(w.gru,scene,h),value=summary}
    end
    return scores,mlp(context,w.value)[1],pending
end
function M.commit(memory,pending)
    if not pending or memory.turn==pending.turn then return end
    memory.hidden=pending.hidden;memory.turn=pending.turn;memory.slots=memory.slots or {}
    memory.slots[#memory.slots+1]={turn=pending.turn,value=pending.value}
    if #memory.slots>32 then table.remove(memory.slots,1) end
end
return M
