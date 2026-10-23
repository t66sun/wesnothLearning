-- Direct Rust/Lua compatibility surface used by the repository's unchanged
-- observation/candidates modules and the shipped Astra. Only public DTOs enter Lua.
local bridge, clock = assert(__bridge), assert(__clock_ms)
__bridge=nil; __clock_ms=nil
local sources=assert(__module_sources)
local rules=bridge('rules',{})
local modules, memories, teacher_memories = {}, {}, {}
local view, units, by_id, legal, last_candidates
local function copy(t)
    if type(t)~='table' then return t end
    local o={};for k,v in pairs(t) do o[k]=copy(v) end
    local meta=getmetatable(t)
    -- Restored JSON arrays may expose a protected boolean metatable.
    -- Keep actual unit methods; plain copied data needs no such marker.
    return type(meta)=='table' and setmetatable(o,meta) or o
end
local function position(x,y)
    if type(x)=='table' then x,y=x.x or x[1],x.y or x[2] end
    if not x or not y or x<1 or y<1 or x>view.width or y>view.height then return nil end
    return (y-1)*view.width+x-1
end
local function coords(p) return p%view.width+1,math.floor(p/view.width)+1 end
local function loc(p) local x,y=coords(p);return {x,y} end
local function rpc(op,args) args=args or {};args.side=view and view.side or nil;return bridge(op,args) end
local function damage_resist(t,kind) return 100-assert(t.resistance[kind],'missing frozen resistance '..kind) end
-- Astra reads native WML child lists for weapon specials and healer detection.
-- The projected configs below contain only the same visible unit definitions.
wml={}
function wml.get_child(cfg,name)
    for _,child in ipairs(cfg) do if child[1]==name then return child[2] end end
end
local methods={}
function methods:clone() return copy(self) end
function methods:defense_on(terrain) return 100-assert(rules.units[self.type].defense[terrain],'missing frozen defense '..terrain) end
function methods:movement_on(terrain) return assert(rules.units[self.type].movement[terrain],'missing frozen movement '..terrain) end
function methods:resistance_against(kind) return damage_resist(rules.units[self.type],kind) end
local function convert(u,existing)
    local t=assert(rules.units[u.unit_type]);local o=existing or {}
    o.id=u.id;o.type=u.unit_type;o.side=u.side;o.x,o.y=coords(u.pos)
    o.hitpoints=u.hp;o.max_hitpoints=(type(u.resolved_max_hp)=='number' and u.resolved_max_hp or t.hp)+(u.feeding_bonus or 0)
    o.moves=u.moves;o.max_moves=type(u.resolved_max_moves)=='number' and u.resolved_max_moves or t.moves
    o.experience=u.xp;o.max_experience=type(u.resolved_max_experience)=='number' and u.resolved_max_experience or t.experience
    o.level=t.level;o.cost=t.cost
    o.alignment=t.alignment;o.canrecruit=u.leader;o.attacks_left=u.attacks_left
    o.status={};for _,s in ipairs(u.status or {}) do o.status[s]=true end
    o.attacks={}
    for wi,w in ipairs(t.weapons) do
        local specials={};for _,s in ipairs(w.specials) do specials[#specials+1]={s,{id=s}} end
        o.attacks[#o.attacks+1]={name=w.id,damage=u.resolved_weapon_damage and u.resolved_weapon_damage[wi] or w.damage,
            number=w.strikes,type=w.damage_type,range=w.range,__cfg={{'specials',specials}}}
    end
    local abilities={};for _,a in ipairs(t.abilities) do
        local tag=(a=='healing' or a=='curing') and 'heals' or a
        abilities[#abilities+1]={tag,{id=a}}
    end
    o.__cfg={{'abilities',abilities}};return setmetatable(o,{__index=methods})
end
local function refresh(v)
    view=v;legal=nil;local old=by_id or {};units={};by_id={}
    for _,u in ipairs(v.units) do local native=convert(u,old[u.id]);units[#units+1]=native;by_id[u.id]=native end
    if wesnoth then
        wesnoth.current.side=v.side;wesnoth.current.turn=v.turn
        wesnoth.current.map.width=v.width;wesnoth.current.map.height=v.height
        for _,s in ipairs(v.sides) do
            local o=wesnoth.sides[s.id] or {};wesnoth.sides[s.id]=o
            o.side=s.id;o.team_name=s.team;o.gold=s.gold;o.recruit=s.recruit or {}
            o.controller='ai';o.eliminated=s.eliminated
            o.fog=s.fog;o.shroud=s.shroud;o.share_view=s.share_view;o.share_maps=s.share_maps
            if s.id==v.side then
                local villages=0;for _,record in pairs(v.villages) do if record[1]==s.id then villages=villages+1 end end
                -- Native total income includes upkeep; Rust returns its exact current
                -- accounting in side views when available. Do not invent hidden income.
                o.total_income=s.total_income or 0
            end
        end
    end
end
local function legal_actions() legal=legal or rpc('legal');return legal end
local function native_at(x,y)
    local p=position(x,y);if not p then return nil end
    for _,u in ipairs(units) do if position(u)==p then return u end end
end
local function adjacent(x,y)
    local dy=x%2==1 and -1 or 1
    local points={{x,y-1},{x,y+1},{x-1,y},{x+1,y},{x-1,y+dy},{x+1,y+dy}}
    local valid={};for _,p in ipairs(points) do if position(p) then valid[#valid+1]=p end end
    local i=0;return function() i=i+1;if valid[i] then return valid[i][1],valid[i][2] end end
end
wesnoth={current={map={}},sides={},units={},unit_types={},paths={atomic_path=true},map={},schedule={}}
function wesnoth.ms_since_init() return clock() end
for id,t in pairs(rules.units) do
    wesnoth.unit_types[id]={id=id,cost=t.cost,hitpoints=t.hp,movement=t.moves,level=t.level,
        alignment=t.alignment,experience=t.experience,advances_to=t.advances_to}
end
function wesnoth.sides.is_enemy(a,b) return wesnoth.sides[a].team_name~=wesnoth.sides[b].team_name end
function wesnoth.sides.is_fogged(side,x,y)
    assert(side==view.side,'host cannot inspect another player view')
    local p=position(x,y);return not p or not view.visible[p+1]
end
function wesnoth.sides.is_shrouded(side,x,y)
    assert(side==view.side,'host cannot inspect another player view')
    local p=position(x,y);return not p or not view.explored[p+1]
end
function wesnoth.units.find_on_map(filter)
    local found={};filter=filter or {}
    for _,u in ipairs(units) do
        if (not filter.side or u.side==filter.side) and (not filter.id or u.id==filter.id)
            and (not filter.x or u.x==filter.x) and (not filter.y or u.y==filter.y) then found[#found+1]=u end
    end
    return found
end
function wesnoth.units.get(x,y) return native_at(x,y) end
function wesnoth.units.clone(u) return u:clone() end
function wesnoth.units.create(cfg)
    local t=assert(rules.units[cfg.type]);local p=assert(position(cfg.x,cfg.y))
    return convert{id=cfg.id or 'detached_probe',unit_type=cfg.type,side=cfg.side,pos=p,
        hp=t.hp,moves=t.moves,xp=0,attacks_left=1,leader=cfg.canrecruit or false,status={}}
end
function wesnoth.map.distance_between(x,y,tx,ty)
    local q=x-1;local r=y-1-math.floor(q/2)
    local tq=tx-1;local tr=ty-1-math.floor(tq/2)
    return math.max(math.abs(q-tq),math.abs(r-tr),math.abs(q+r-tq-tr))
end
function wesnoth.map.get_owner(p)
    local k=position(p);local known=k and view.villages[tostring(k)]
    return known and known[1] or nil
end
local function terrain_match(code,pattern)
    for part in pattern:gmatch('[^,]+') do
        local escaped=part:gsub('([%.%+%-%^%$%(%)%%%.%[%]])','%%%1'):gsub('%*','.*'):gsub('%?','.')
        if code:match('^'..escaped..'$') then return true end
    end
    return false
end
function wesnoth.map.find(filter)
    local found={}
    for i,code in ipairs(view.terrain) do
        if type(code)=='string' then
            local t=rules.terrains[code]
            if (not filter.gives_income or t.village) and (not filter.terrain or terrain_match(code,filter.terrain)) then found[#found+1]=loc(i-1) end
        end
    end
    return found
end
function wesnoth.current.map:iter_adjacent(x,y) return adjacent(x,y) end
setmetatable(wesnoth.current.map,{__index=function(_,p)
    if type(p)=='table' then local i=position(p);local code=i and view.terrain[i+1];return type(code)=='string' and code or '_s' end
end})
function wesnoth.paths.find_reach(u,options)
    local result={};for _,p in ipairs(rpc('reach',{id=u.id,moves=u.moves})) do
        local x,y=coords(p[1]);result[#result+1]={x,y,p[2]}
    end
    return result
end
function wesnoth.paths.find_path(u,x,y,options)
    local result=rpc('path',{id=u.id,to=assert(position(x,y))})
    local path={};for _,p in ipairs(result.path) do path[#path+1]=loc(p) end
    return path,result.cost
end
function wesnoth.schedule.get_time_of_day() return {lawful_bonus=rules.lawful_bonus[(view.turn-1)%#rules.lawful_bonus+1]} end
function wesnoth.simulate_combat(u,weapon,target)
    local result=rpc('forecast',{attacker=u.id,target=target.id,weapon=weapon-1,pos=position(u)})
    local function decode(c)
        local chance={};for hp,p in pairs(c.hp_chance) do chance[tonumber(hp)]=p end
        c.hp_chance=chance;return c
    end
    return decode(result.attacker),decode(result.defender)
end
local helper={}
function helper.get_attackable_enemies()
    local enemies={};for _,u in ipairs(units) do if wesnoth.sides.is_enemy(view.side,u.side) and not u.status.petrified then enemies[#enemies+1]=u end end
    return enemies
end
local function require_module(path)
    if path=='ai/lua/ai_helper.lua' then return helper end
    local name=path:match('([^/]+)$')
    -- Preserve Astra's own module names separately from common bot.lua.
    if path:find('gpt6astra',1,true) then name='astra/'..name end
    if modules[name] then return modules[name] end
    local source=assert(sources[name],'unimplemented host module '..path)
    local result=assert(load(source,'@'..name,'t',_ENV))();modules[name]=result;return result
end
wesnoth.require=require_module;wesnoth.dofile=require_module
ai={}
local function to_unit(u) if u.id then return u else return native_at(u) end end
function ai.check_move(u,x,y)
    u=to_unit(u);local p=position(x,y);if not u then return {ok=false} end
    for _,a in ipairs(legal_actions()) do if a.kind=='move' and a.unit==u.id and a.to==p then return {ok=true} end end
    return {ok=false}
end
function ai.check_recruit(name,p)
    p=position(p);for _,a in ipairs(legal_actions()) do if a.kind=='recruit' and a.unit_type==name and a.to==p then return {ok=true} end end
    return {ok=false}
end
function ai.check_attack(u,e,weapon)
    u,e=to_unit(u),to_unit(e);if not u or not e then return {ok=false} end
    for _,a in ipairs(legal_actions()) do if a.kind=='attack' and a.unit==u.id and a.target==e.id and a.weapon==weapon-1 then return {ok=true} end end
    return {ok=false}
end
local events={}
local function perform(action)
    local result=rpc('step',{action=action});refresh(result.view);events[#events+1]=result.result
    local interrupted=result.result.interrupted
    return {ok=not interrupted,gamestate_changed=true,status=interrupted and 2005 or 0}
end
function ai.move(u,p) u=assert(to_unit(u));return perform{kind='move',unit=u.id,to=assert(position(p)),full=false} end
function ai.move_full(u,p) u=assert(to_unit(u));return perform{kind='move',unit=u.id,to=assert(position(p)),full=true} end
function ai.recruit(name,p) return perform{kind='recruit',unit_type=name,to=assert(position(p))} end
function ai.attack(u,e,weapon) u,e=assert(to_unit(u)),assert(to_unit(e));return perform{kind='attack',unit=u.id,target=e.id,weapon=weapon-1} end

function lite_decision(side,budget_ms,teacher,generate_candidates)
    refresh(bridge('view',{side=side}))
    local O=require_module('observation.lua');local C=require_module('candidates.lua')
    memories[side]=memories[side] or {};local obs=O.capture(memories[side],side)
    local candidates,timing
    if generate_candidates==false then
        -- Unrecorded Astra seats and diagnostic terminal observations need no
        -- candidate search. Teacher planning below remains unchanged.
        local schema=require_module('features.lua')
        candidates={{kind='end_turn',features=O.normalize({end_turn=1},schema.action_features),rule=-1}}
        require_module('spatial.lua').actions(obs,candidates)
        timing={truncated=false,ms=0,predictions=0,work=0}
    else
        candidates,timing=C.generate(obs,budget_ms)
    end
    last_candidates=candidates
    local labels=rpc('reward_labels')
    local W=require_module('rewards.lua')
    local raw=W.capture(obs,obs.memory,{judge=false,total_strategic_weight=labels.total_strategic_weight,
        shared_exploration_members={side},shared_exploration_scope=tostring(side)})
    raw.economy=labels.economy;raw.explored=labels.explored
    local teacher_action
    teacher_memories[side]=teacher_memories[side] or {owners={},home={}}
    local ledger=teacher_memories[side]
    for _,u in ipairs(obs.own) do if not ledger.home[u.id] then ledger.home[u.id]={u.x,u.y} end end
    -- Astra indexes remembered villages by x*1000+y, not observation's "x,y".
    -- Both consumers must see the same last legally observed ownership.
    ledger.owners={}
    for key,owner in pairs(obs.memory.villages or {}) do
        local x,y=key:match('^(%d+),(%d+)$')
        if x then ledger.owners[tonumber(x)*1000+tonumber(y)]=owner end
    end
    if teacher then
        local strategy=#view.sides==2 and 'duel' or #view.sides==4 and 'four' or nil
        assert(strategy,'Astra host supports two/four player games')
        local astra=require_module('~add-ons/gpt6astra/lua/'..strategy..'.lua')
        local probe=copy(ledger)
        astra:evaluation({},probe);teacher_action=copy(probe.plan)
        if not teacher_action then teacher_action={kind='end_turn'} end
    end
    return {global=obs.global,opponents=obs.opponents,spatial=obs.spatial,candidates=candidates,timing=timing,
        side=side,turn=view.turn,teacher_action=teacher_action,potential=obs.potential,reward_raw=raw,
        engine_id='lite-0.1',approximate=true}
end
function lite_execute(action)
    local side=view.side;events={}
    local O=require_module('observation.lua');local C=require_module('candidates.lua')
    local obs=O.capture(memories[side] or {},side)
    local schema=require_module('features.lua')
    if not action.features then action.features=O.normalize({[action.kind]=1},schema.action_features) end
    local prior=require_module('spatial.lua').memory_observation(obs)
    local diagnostics=C.diagnostics(obs,action,last_candidates)
    local execution
    if action.kind=='end_turn' then perform{kind='end_turn'};execution={changed=true} else execution=C.execute(action) end
    if not execution or execution.changed then C.remember(obs,action) end
    C.outcome(action,diagnostics)
    local post=O.capture(memories[side] or {},side);local labels=rpc('reward_labels')
    local raw=require_module('rewards.lua').capture(post,post.memory,{judge=false,
        total_strategic_weight=labels.total_strategic_weight,shared_exploration_members={side},shared_exploration_scope=tostring(side)})
    raw.economy=labels.economy;raw.explored=labels.explored
    local changed=execution and execution.changed or false
    local write=action.kind=='end_turn' and prior or require_module('spatial.lua').memory_observation(post)
    return {events=events,diagnostics=diagnostics,view=view,reward_after=raw,execution=execution,committed=changed,memory_write=changed and write or nil}
end
local function string_keys(map)
    local out={};for k,v in pairs(map) do out[tostring(k)]=v end;return out
end
function lite_snapshot()
    -- Side IDs form sparse maps (e.g. enemies 2/4 in a team game), not Lua
    -- arrays. JSON requires string keys; restore rehydrates them as side IDs.
    local saved,teachers={},{}
    for side,memory in pairs(memories) do
        local m={};for k,v in pairs(memory) do m[k]=v end
        m.seen=string_keys(memory.seen or {});saved[tostring(side)]=m
    end
    for side,memory in pairs(teacher_memories) do
        local m={};for k,v in pairs(memory) do m[k]=v end
        m.owners=string_keys(memory.owners or {});teachers[tostring(side)]=m
    end
    return {memory=saved,teacher_memory=teachers,
        exploration=_G.__wesnoth_learning_exploration_v5 or {}}
end
function lite_restore(saved)
    local function hydrate(value)
        if type(value)~='table' then return end
        if value.type and value.max_hitpoints and rules.units[value.type] then setmetatable(value,{__index=methods}) end
        for _,v in pairs(value) do hydrate(v) end
    end
    hydrate(saved)
    memories={};teacher_memories={}
    for s,m in pairs(saved.memory or {}) do
        local seen={};for id,value in pairs(m.seen or {}) do seen[tonumber(id) or id]=value end
        m.seen=seen;memories[tonumber(s) or s]=m
    end
    for s,m in pairs(saved.teacher_memory or {}) do
        local owners={};for key,owner in pairs(m.owners or {}) do owners[tonumber(key) or key]=owner end
        m.owners=owners;teacher_memories[tonumber(s) or s]=m
    end
    local scopes=_G.__wesnoth_learning_exploration_v5 or {};_G.__wesnoth_learning_exploration_v5=scopes
    for k in pairs(scopes) do scopes[k]=nil end
    for k,v in pairs(saved.exploration or {}) do scopes[k]=v end
    view=nil;units=nil;by_id=nil;legal=nil
end
