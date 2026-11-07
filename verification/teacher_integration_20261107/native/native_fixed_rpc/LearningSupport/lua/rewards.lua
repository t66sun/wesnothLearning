-- Training-only labels. Never attach this module's output to spatial/global.
-- Public influence uses only obs.tiles, own/visible friends, and legal history.
local M={formula_id='v5-potential-1'}
-- All exported policy add-ons and LearningSupport run in the same game Lua
-- kernel. Keep only the exploration ledger shared across require() paths.
-- Individual actor memory receives solely its permitted scope, never this map.
local scopes=rawget(_G,'__wesnoth_learning_exploration_v5')
if not scopes then scopes={};rawset(_G,'__wesnoth_learning_exploration_v5',scopes) end
local function clear_scopes() for scope in pairs(scopes) do scopes[scope]=nil end end
local function key(x,y) return x..','..y end
local function truth(v) return v==true or v=='yes' end
local function visible(side,x,y)
    return not wesnoth.sides.is_fogged(side,x,y) and not wesnoth.sides.is_shrouded(side,x,y)
end
local function strategic(terrain,x,y)
    -- Max weight, never additive: villages 4, keeps 2, passages/coarse grid 1.
    if terrain:find('%^V') then return 4 end
    if terrain:match('^K') then return 2 end
    if terrain:match('^R') or (x%4==1 and y%4==1) then return 1 end
    return 0
end
local function neighbors(x,y)
    local offset=x%2
    return {{x,y-1},{x,y+1},{x-1,y-offset},{x-1,y+1-offset},{x+1,y-offset},{x+1,y+1-offset}}
end
local function push(heap,item)
    local i=#heap+1;heap[i]=item
    while i>1 do local p=math.floor(i/2);if heap[p][1]<=item[1] then break end;heap[i]=heap[p];i=p;heap[i]=item end
end
local function pop(heap)
    local top=heap[1];local last=table.remove(heap)
    if #heap>0 then
        local i=1;heap[1]=last
        while i*2<=#heap do
            local c=i*2;if c<#heap and heap[c+1][1]<heap[c][1] then c=c+1 end
            if heap[c][1]>=last[1] then break end
            heap[i]=heap[c];i=c;heap[i]=last
        end
    end
    return top
end
local function flood(tiles,costs,sources)
    local distances,heap={},{}
    for _,s in ipairs(sources) do
        local k=key(s.x,s.y);local strength=math.max(0,math.min(1,s.strength))*math.exp(-.25*s.age)
        local d=strength>0 and -math.log(strength)*24 or math.huge
        if tiles[k] and d<=24 and d<(distances[k] or math.huge) then distances[k]=d;push(heap,{d,s.x,s.y}) end
    end
    while #heap>0 do
        local item=pop(heap);local d,x,y=item[1],item[2],item[3]
        if distances[key(x,y)]==d then
            for _,p in ipairs(neighbors(x,y)) do
                local k=key(p[1],p[2]);local cost=costs[k]
                local nextd=cost and d+cost or math.huge
                if nextd<=24 and nextd<(distances[k] or math.huge) then distances[k]=nextd;push(heap,{nextd,p[1],p[2]}) end
            end
        end
    end
    local result={};for k,d in pairs(distances) do result[k]=math.exp(-d/24) end;return result
end
local function roster(obs)
    if obs.memory.roster then return obs.memory.roster end
    local result={};for i,s in ipairs(wesnoth.sides) do if s.controller~='null' then result[#result+1]=i end end;return result
end
function M.judge_economy(obs)
    -- Deliberate judge-only query. Its scalar never enters a policy observation.
    local groups,group_for,amounts={},{},{}
    for _,side in ipairs(roster(obs)) do amounts[side]=wesnoth.sides[side].gold end
    for _,u in ipairs(wesnoth.units.find_on_map{}) do
        if amounts[u.side] then amounts[u.side]=amounts[u.side]+wesnoth.unit_types[u.type].cost*math.max(0,u.hitpoints)/math.max(1,u.max_hitpoints) end
    end
    for _,p in ipairs(wesnoth.map.find{gives_income=true}) do
        local side=wesnoth.map.get_owner(p)
        if amounts[side] then amounts[side]=amounts[side]+20 end
    end
    for _,side in ipairs(roster(obs)) do
        local group=side
        for _,other in ipairs(roster(obs)) do
            if other<group and not wesnoth.sides.is_enemy(side,other) then group=other end
        end
        group_for[side]=group;groups[group]=groups[group] or {sum=0,n=0}
        groups[group].sum=groups[group].sum+amounts[side];groups[group].n=groups[group].n+1
    end
    local own=group_for[obs.side];local total,others,n=200,0,0
    for group,g in pairs(groups) do
        g.mean=g.sum/g.n;total=total+math.abs(g.mean)
        if group~=own then others=others+g.mean;n=n+1 end
    end
    return n>0 and (groups[own].mean-others/n)/total or 0
end
local function exploration(obs,state,options)
    local side=wesnoth.sides[obs.side]
    if not truth(side.fog) then return 0 end
    local members={obs.side}
    -- Directed sharing is not assumed reciprocal. A caller may supply the exact
    -- scope/members if a scenario implements more complex WML sharing rules.
    for _,s in ipairs(roster(obs)) do
        local other=wesnoth.sides[s]
        if s~=obs.side and not wesnoth.sides.is_enemy(obs.side,s) and
            ((truth(side.share_view) and truth(other.share_view)) or (truth(side.share_maps) and truth(other.share_maps))) then
            members[#members+1]=s
        end
    end
    if options.shared_exploration_members then members=options.shared_exploration_members end
    table.sort(members)
    local scope=options.shared_exploration_scope or table.concat(members,':')
    local ledger=options.shared_ledger or scopes
    ledger[scope]=ledger[scope] or {seen={},earned=0,initialized=false}
    local shared=ledger[scope];local initial=not shared.initialized
    local w,h=wesnoth.current.map.width,wesnoth.current.map.height
    local new=0
    for x=1,w do for y=1,h do
        local seen=false
        for _,s in ipairs(members) do if visible(s,x,y) then seen=true;break end end
        local k=key(x,y)
        if seen and not shared.seen[k] then shared.seen[k]=true;if not initial then new=new+1 end end
    end end
    shared.initialized=true;shared.earned=math.min(1,shared.earned+new/(options.total_explorable_weight or w*h))
    state.exploration=shared
    return shared.earned
end
local function signature(u)
    local result={}
    for _,t in ipairs{'Gg','Hh','Ww','Mm'} do result[#result+1]=u:movement_on(t) end
    return result
end
local function control(obs,state,options)
    -- Deployment has no need for a training reward. Without an explicitly
    -- supplied normalization scalar, only the training judge may inspect the
    -- full map to obtain one.
    if not options.judge and not options.total_strategic_weight then return .5 end
    local turn=wesnoth.current.turn;state.enemies=state.enemies or {};state.templates=state.templates or {}
    local legal={};for _,u in ipairs(obs.friends) do legal[#legal+1]={unit=u,enemy=false,age=0} end
    local current={}
    for _,u in ipairs(obs.enemies) do
        current[u.id]=true
        -- Store only fields visible now. Retain a detached legal type template.
        state.enemies[u.id]={id=u.id,type=u.type,x=u.x,y=u.y,hp=u.hitpoints,max_hp=u.max_hitpoints,turn=turn}
        -- A detached copy preserves only information legally observed now and
        -- does not create random traits/names or consume the combat RNG.
        state.templates[u.id]=wesnoth.units.clone(u)
    end
    local ids={};for id in pairs(state.enemies) do ids[#ids+1]=id end;table.sort(ids)
    for _,id in ipairs(ids) do
        local e=state.enemies[id]
        if not current[id] and visible(obs.side,e.x,e.y) then state.enemies[id]=nil;state.templates[id]=nil
        else
            legal[#legal+1]={unit=state.templates[id],enemy=true,age=math.max(0,turn-e.turn),x=e.x,y=e.y,hp=e.hp,max_hp=e.max_hp}
        end
    end
    local classes={}
    for _,source in ipairs(legal) do
        local u=source.unit;local sig=signature(u);local best,distance=nil,math.huge
        for i,c in ipairs(classes) do
            local d=0;for j=1,4 do d=d+math.abs(sig[j]-c.signature[j]) end
            if d<distance then best=i;distance=d end
        end
        if not best or (distance>0 and #classes<4) then
            classes[#classes+1]={signature=sig,template=u,own={},enemy={}};best=#classes
        end
        local c=classes[best];local list=source.enemy and c.enemy or c.own
        list[#list+1]={x=source.x or u.x,y=source.y or u.y,
            strength=(source.hp or u.hitpoints)/math.max(1,source.max_hp or u.max_hitpoints),age=source.age}
    end
    local tile_keys={};for k in pairs(obs.tiles) do tile_keys[#tile_keys+1]=k end;table.sort(tile_keys)
    local identity={tostring(turn)}
    for _,k in ipairs(tile_keys) do identity[#identity+1]=k..'='..obs.tiles[k].terrain end
    for i,c in ipairs(classes) do
        identity[#identity+1]=i..':'..table.concat(c.signature,',')
        for _,name in ipairs{'own','enemy'} do for _,s in ipairs(c[name]) do identity[#identity+1]=name..':'..key(s.x,s.y)..':'..s.strength..':'..s.age end end
    end
    local cache_key=table.concat(identity,';')
    if state.control_key==cache_key then return state.control_value end
    local own,enemy={},{}
    for _,c in ipairs(classes) do
        local costs={}
        for _,k in ipairs(tile_keys) do
            local cost=c.template:movement_on(obs.tiles[k].terrain)
            if cost>0 and cost<99 then costs[k]=cost end
        end
        for _,name in ipairs{'own','enemy'} do
            local target=name=='own' and own or enemy
            for k,value in pairs(flood(obs.tiles,costs,c[name])) do target[k]=math.max(target[k] or 0,value) end
        end
    end
    if not state.total_strategic_weight and not options.total_strategic_weight then
        -- Judge normalization is a scalar. Unknown locations/terrain stay here.
        local total=0;local w,h=wesnoth.current.map.width,wesnoth.current.map.height
        for x=1,w do for y=1,h do total=total+strategic(wesnoth.current.map[{x,y}],x,y) end end
        state.total_strategic_weight=math.max(1,total)
    end
    local total=options.total_strategic_weight or state.total_strategic_weight
    local score=.5*total
    for _,k in ipairs(tile_keys) do
        local tile=obs.tiles[k];local a,b=own[k] or 0,enemy[k] or 0
        local fraction=a+b>1e-12 and a/(a+b) or .5
        score=score+strategic(tile.terrain,tile.x,tile.y)*(fraction-.5)
    end
    state.control_key=cache_key;state.control_value=math.max(0,math.min(1,score/total))
    return state.control_value
end
function M.capture(obs,memory,training)
    local options=type(training)=='table' and training or {judge=training==true}
    if options.preview then
        local function copy(v) if type(v)~='table' then return v end;local out={};for k,x in pairs(v) do out[k]=copy(x) end;return out end
        options=copy(options);options.shared_ledger=copy(options.shared_ledger or scopes)
        memory=copy(memory or obs.memory)
    end
    memory=memory or obs.memory;memory.reward=memory.reward or {}
    local state=memory.reward
    local raw={economy=0,control=control(obs,state,options),explored=exploration(obs,state,options)}
    if options.judge then raw.economy=M.judge_economy(obs) end
    return raw
end
function M.initialize_all(options)
    -- Invoke after initial units and fog/shroud are established, before ANY
    -- side executes an action. All starting views are excluded together.
    options=options or {};clear_scopes()
    local members={}
    for side,s in ipairs(wesnoth.sides) do if s.controller~='null' then members[#members+1]=side end end
    for _,side in ipairs(members) do
        exploration({side=side,memory={roster=members}},{},options)
    end
end
function M.reset() clear_scopes() end
return M
