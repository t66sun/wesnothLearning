-- Training/differential transport only. Actions still execute in Wesnoth 1.18.8.
local M={}
local O=wesnoth.require '~add-ons/LearningNativeRPC/lua/observation.lua'
local C=wesnoth.require '~add-ons/LearningNativeRPC/lua/candidates.lua'
local S=wesnoth.require '~add-ons/LearningNativeRPC/lua/spatial.lua'
local W=wesnoth.require '~add-ons/LearningNativeRPC/lua/rewards.lua'
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local session=rawget(_G,'__learning_native_rpc')
if not session then session=wesnoth.dofile '~add-ons/LearningNativeRPC/session.lua';rawset(_G,'__learning_native_rpc',session) end
local NULL={}
local function array(t) return setmetatable(t or {},{__array=true}) end
local function copy(value)
    if type(value)~='table' then return value end
    local result={};for key,item in pairs(value) do result[key]=copy(item) end
    return setmetatable(result,getmetatable(value))
end
local function json(v)
    if v==NULL or v==nil then return 'null' end
    local kind=type(v)
    if kind=='boolean' then return v and 'true' or 'false' end
    if kind=='number' then assert(v==v and math.abs(v)<math.huge,'nonfinite RPC number');return string.format('%.17g',v) end
    if kind=='string' then return '"'..v:gsub('[%z\1-\31\\"]',function(c) return string.format('\\u%04x',c:byte()) end)..'"' end
    assert(kind=='table','RPC cannot serialize native handles')
    local out={}
    if #v>0 or (getmetatable(v) or {}).__array then
        for _,x in ipairs(v) do out[#out+1]=json(x) end;return '['..table.concat(out,',')..']'
    end
    for k,x in pairs(v) do out[#out+1]=json(tostring(k))..':'..json(x) end
    table.sort(out);return '{'..table.concat(out,',')..'}'
end
local function emit(kind,payload) std_print('NATIVE_RPC '..session.token..' '..json {kind=kind,id=session.last_id,payload=payload}) end
local function position(x,y) return (y-1)*session.spec.width+x-1 end
local function coords(p) return p%session.spec.width+1,math.floor(p/session.spec.width)+1 end
local function frame() return {turn=wesnoth.current.turn,current_side=wesnoth.current.side,finished=judge.done(),truncated=false} end
local function capture(side)
    assert(wesnoth.sides[side],'invalid viewing side')
    session.memories[side]=session.memories[side] or {}
    return O.capture(session.memories[side],side)
end
local function unit(u)
    local status=array();for _,s in ipairs {'poisoned','slowed','petrified','stunned','unpoisonable','undrainable','unplagueable'} do if u.status[s] then status[#status+1]=s end end
    return {id=u.id,unit_type=u.type,side=u.side,pos=position(u.x,u.y),hp=u.hitpoints,moves=u.moves,
        attacks_left=u.attacks_left,xp=u.experience,leader=u.canrecruit or false,status=status,traits=array(),
        resolved_max_hp=u.max_hitpoints,resolved_max_moves=u.max_moves,resolved_max_experience=u.max_experience}
end
local function observe(side)
    local obs=capture(side);local terrain,visible,explored,units,sides=array(),array(),array(),array(),array()
    local villages={};local memory=obs.memory
    memory.rpc_last_seen=memory.rpc_last_seen or {};memory.rpc_village_turns=memory.rpc_village_turns or {}
    for y=1,session.spec.height do for x=1,session.spec.width do
        local key=x..','..y;local tile=obs.tiles[key]
        terrain[#terrain+1]=tile and tile.terrain or NULL
        visible[#visible+1]=tile and tile.visible or false;explored[#explored+1]=tile~=nil
        if memory.villages[key]~=nil then
            if tile and tile.visible then memory.rpc_village_turns[key]=wesnoth.current.turn end
            villages[tostring(position(x,y))]=array {memory.villages[key],memory.rpc_village_turns[key] or 1}
        end
    end end
    local now={}
    for _,u in ipairs(obs.friends) do units[#units+1]=unit(u);now[u.id]=true end
    for _,u in ipairs(obs.enemies) do
        local item=unit(u);units[#units+1]=item;now[u.id]=true
        memory.rpc_last_seen[u.id]={unit=item,turn=wesnoth.current.turn}
    end
    for id,seen in pairs(memory.rpc_last_seen) do
        local x,y=coords(seen.unit.pos);local tile=obs.tiles[x..','..y]
        if tile and tile.visible and not now[id] then memory.rpc_last_seen[id]=nil end
    end
    table.sort(units,function(a,b) return a.id<b.id end)
    for i,s in ipairs(wesnoth.sides) do
        local original=session.spec.sides[i]
        sides[#sides+1]={id=i,team=original.team or tostring(i),eliminated=judge.done() and #wesnoth.units.find_on_map{side=i,canrecruit=true}==0 or false,
            gold=i==side and s.gold or NULL,base_income=i==side and original.base_income or NULL,
            total_income=i==side and s.total_income or NULL,recruit=i==side and array(s.recruit) or NULL,
            fog=original.fog or false,shroud=original.shroud or false,share_view=original.share_view or false,share_maps=original.share_maps or false}
    end
    local result=frame();result.engine_id='native-1.18.8';result.rng_version='native-1.18.8';result.rules_version='native-1.18.8'
    result.approximate=false;result.side=side;result.width=session.spec.width;result.height=session.spec.height
    result.terrain=terrain;result.visible=visible;result.explored=explored;result.units=units;result.sides=sides
    result.villages=villages;result.last_seen=memory.rpc_last_seen;result.winner=NULL
    return result
end
local function candidates(side)
    assert(side==wesnoth.current.side,'legal actions require the active side')
    local obs=capture(side);local actions,timing=C.generate(obs);return obs,actions,timing
end
local function teacher(obs,requested)
    session.teacher_memories=session.teacher_memories or {}
    local ledger=session.teacher_memories[obs.side] or {owners={},home={}}
    session.teacher_memories[obs.side]=ledger
    for _,u in ipairs(obs.own) do if not ledger.home[u.id] then ledger.home[u.id]={u.x,u.y} end end
    for key,owner in pairs(obs.memory.villages or {}) do
        local x,y=key:match('^(%d+),(%d+)$')
        if x then ledger.owners[tonumber(x)*1000+tonumber(y)]=owner end
    end
    if not requested then return nil end
    local strategy=#wesnoth.sides==2 and 'duel' or #wesnoth.sides==4 and 'four' or nil
    assert(strategy,'Astra native host supports two/four player games')
    local astra=wesnoth.require('~add-ons/gpt6astra/lua/'..strategy..'.lua')
    local probe=copy(ledger)
    local started=wesnoth.ms_since_init()
    local ok,reason=pcall(astra.evaluation,astra,{},probe)
    local elapsed=wesnoth.ms_since_init()-started
    if not ok then return nil,tostring(reason),elapsed end
    return copy(probe.plan or {kind='end_turn'}),nil,elapsed
end
local function primitive(candidate,obs)
    if candidate.kind=='end_turn' then return {kind='end_turn'} end
    if candidate.kind=='recruit' then return {kind='recruit',unit_type=candidate.type,to=position(candidate.x,candidate.y)} end
    local actor=obs.occupied[candidate.x..','..candidate.y]
    if candidate.kind=='move' then return {kind='move',unit=actor.id,to=position(candidate.tx,candidate.ty),full=candidate.full} end
    if candidate.kind=='attack' then local target=obs.occupied[candidate.tx..','..candidate.ty];return {kind='attack',unit=actor.id,target=target.id,weapon=candidate.weapon-1} end
end
local function legal(side)
    assert(side==wesnoth.current.side,'legal actions require active side')
    local obs=capture(side);local actions=array {{kind='end_turn'}}
    for _,u in ipairs(obs.own) do
        if u.moves>0 then for _,p in ipairs(wesnoth.paths.find_reach(u,{viewing_side=side,ignore_visibility=false})) do
            if not obs.occupied[p[1]..','..p[2]] and ai.check_move(u,p[1],p[2]).ok then actions[#actions+1]={kind='move',unit=u.id,to=position(p[1],p[2]),full=false} end
        end end
        if u.attacks_left>0 then for _,e in ipairs(obs.enemies) do if wesnoth.map.distance_between(u.x,u.y,e.x,e.y)==1 then
            for wi=1,#u.attacks do if ai.check_attack(u,e,wi).ok then actions[#actions+1]={kind='attack',unit=u.id,target=e.id,weapon=wi-1} end end
        end end end
    end
    local castles={};for _,tile in pairs(obs.tiles) do if tile.terrain:match('^[CK]') then castles[#castles+1]=tile end end
    table.sort(castles,function(a,b) return position(a.x,a.y)<position(b.x,b.y) end)
    for _,name in ipairs(wesnoth.sides[side].recruit) do for _,tile in ipairs(castles) do
        if not obs.occupied[tile.x..','..tile.y] and ai.check_recruit(name,{tile.x,tile.y}).ok then actions[#actions+1]={kind='recruit',unit_type=name,to=position(tile.x,tile.y)} end
    end end
    return {actions=actions}
end
local function action_intent(a)
    if a.kind=='end_turn' then return a end
    if a.kind=='recruit' then local x,y=coords(a.to);return {kind='recruit',type=a.unit_type,x=x,y=y} end
    local own=wesnoth.units.find_on_map {side=wesnoth.current.side,id=a.unit};local u=assert(own[1],'acting unit missing')
    if a.kind=='move' then local x,y=coords(a.to);return {kind='move',x=u.x,y=u.y,tx=x,ty=y,full=a.full or false} end
    local obs=capture(wesnoth.current.side);local target
    for _,e in ipairs(obs.enemies) do if e.id==a.target then target=e end end
    assert(target,'target is not legally visible')
    return {kind='attack',x=u.x,y=u.y,tx=target.x,ty=target.y,weapon=a.weapon+1}
end
function M.initialize()
    if session.initialized then return end;session.initialized=true
    for _,u in ipairs(session.spec.units) do
        local x,y=coords(u.pos)
        assert(not u.traits or #u.traits==0 or u.native_cfg,'native traits require captured native_cfg')
        local cfg=u.native_cfg or {id=u.id,type=u.unit_type,side=u.side,x=x,y=y,canrecruit=u.leader or false,
            hitpoints=u.hp,moves=u.moves,attacks_left=u.attacks_left,experience=u.xp or 0,random_traits=false,random_gender=false,generate_name=false}
        local created=wesnoth.units.create(cfg)
        for _,status in ipairs(u.status or {}) do created.status[status]=true end
        wesnoth.units.to_map(created)
    end
    for p,owner in pairs(session.spec.village_owner or {}) do local x,y=coords(tonumber(p));wesnoth.map.set_owner({x,y},owner) end
    local check=judge.check
    judge.check=function() if session.executing then session.needs_check=true else check() end end
    session.check=check
end
function M:evaluation(cfg,data)
    if not session.reward_initialized then
        -- Native turn-start refresh may precede the first CA; reset the requested
        -- initial dynamic values once so GameSpec denotes the first controllable state.
        for _,original in ipairs(session.spec.units) do
            local units=wesnoth.units.find_on_map{id=original.id,side=original.side};local u=assert(units[1])
            u.hitpoints=original.hp;u.moves=original.moves;u.attacks_left=original.attacks_left;u.experience=original.xp or 0
        end
        for _,s in ipairs(session.spec.sides) do
            local side=wesnoth.sides[s.id];side.gold=s.gold
            -- Multiplayer faction setup can replace scenario recruits. Apply the
            -- requested list after setup, before observations and reward capture.
            local recruits={};for i,name in ipairs(s.recruit or {}) do recruits[i]=name end
            side.recruit=recruits
        end
        if session.spec.differential_probe then
            session.differential_probe=wesnoth.require '~add-ons/LearningNativeRPC/differential_probe.lua'
            session.differential_probe.initialize()
        end
        W.initialize_all();session.reward_initialized=true
    end
    while not judge.done() do
        emit('READY',frame())
        local command
        repeat
            command=wesnoth.dofile '~add-ons/LearningNativeRPC/command.lua'
            if not command or command.id<=session.last_id then
                assert(wesnoth.interface and wesnoth.interface.delay,'native delay API unavailable');wesnoth.interface.delay(10)
            end
        until command and command.id>session.last_id
        assert(command.token==session.token and command.id==session.last_id+1,'native RPC command sequence/token mismatch')
        session.last_id=command.id
        if command.kind=='observe' then emit('OBS',observe(command.side))
        elseif command.kind=='legal_actions' then emit('ACTIONS',legal(command.side))
        elseif command.kind=='decision' then
            local obs,actions,timing=candidates(command.side)
            -- Freeze student candidates first. Astra's evaluation receives only a
            -- disposable copy of the independent public-history ledger.
            local teacher_action,teacher_skipped,teacher_ms=teacher(obs,command.teacher)
            timing.teacher_ms=teacher_ms
            emit('DECISION',{global=obs.global,opponents=obs.opponents,spatial=obs.spatial,candidates=actions,timing=timing,
                side=command.side,turn=wesnoth.current.turn,teacher_action=teacher_action,teacher_skipped=teacher_skipped,
                potential=obs.potential,reward_raw=W.capture(obs,obs.memory,true)})
        elseif command.kind=='step' or command.kind=='execute_candidate' then
            data.rpc_action=command.kind=='step' and action_intent(command.action) or command.action
            return 100000
        else error('unknown native RPC request '..tostring(command.kind)) end
    end
    return 0
end
function M:execution(cfg,data)
    local a=assert(data.rpc_action);local side=wesnoth.current.side;local obs=capture(side)
    if session.differential_probe then session.differential_probe.before(a) end
    session.executing=true
    local ok,result=pcall(C.execute,a)
    session.executing=false
    if not ok then emit('ERROR',{error=tostring(result)});error(result) end
    assert(type(result)=='table' and type(result.changed)=='boolean','action omitted changed outcome')
    if result.changed then C.remember(obs,a) end
    local post=capture(side);local raw=W.capture(post,post.memory,true)
    local output={changed=result.changed,interrupted=result.interrupted or false,intent=a,committed=result.changed,
        reward_after=raw,memory_write=result.changed and S.memory_observation(post) or nil,view=observe(side)}
    if session.differential_probe then output.differential=session.differential_probe.after() end
    emit('OUTCOME',output)
    session.check()
    if a.kind=='end_turn' then wesnoth.wml_actions.end_turn {} end
end
return M
