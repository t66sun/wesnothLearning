-- The only live-game read boundary. Search modules receive plain public data.
local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local P={}
local damage_types={'blade','pierce','impact','fire','cold','arcane'}
function P.profile(u,terrain_codes)
    local p={id=u.id,type=u.type,side=u.side,x=u.x,y=u.y,hp=u.hitpoints,max_hp=u.max_hitpoints,
        moves=u.moves,max_moves=u.max_moves,attacks_left=u.attacks_left,level=u.level or 1,
        leader=u.canrecruit or false,cost=u.cost or wesnoth.unit_types[u.type].cost,
        xp=u.experience or 0,max_xp=u.max_experience or 999,alignment=u.alignment,
        slow=u.status.slowed or false,poison=u.status.poisoned or false,petrified=u.status.petrified or false,
        unpoisonable=u.status.unpoisonable or false,undrainable=u.status.undrainable or false,
        resistance={},movement={},defense={},weapons={}}
    for _,kind in ipairs(damage_types) do p.resistance[kind]=u:resistance_against(kind) end
    for code in pairs(terrain_codes) do p.movement[code]=u:movement_on(code);p.defense[code]=u:defense_on(code) end
    for _,a in ipairs(u.attacks) do
        local w={damage=a.damage,number=a.number,type=a.type,range=a.range,
            accuracy=a.accuracy or 0,parry=a.parry or 0,defense_weight=a.defense_weight or 1}
        for _,tag in ipairs(wml.get_child(a.__cfg,'specials') or {}) do
            local name=tag[2].id or tag[1]
            if tag[1]=='slow' or tag[1]=='poison' or tag[1]=='firststrike' or tag[1]=='drains' or tag[1]=='berserk' or tag[1]=='plague' then
                w[tag[1]]=true
            elseif name=='charge' or name=='backstab' or name=='magical' or name=='marksman' then w[name]=true
            else p.unsupported=true end
        end
        p.weapons[#p.weapons+1]=w
    end
    for _,tag in ipairs(wml.get_child(u.__cfg,'abilities') or {}) do
        local kind=tag[1]
        if kind=='skirmisher' then p.skirmisher=true
        elseif kind=='leadership' then p.leadership=true
        elseif kind=='illuminates' then p.illuminates=true
        elseif kind=='heals' then p.healing=math.max(p.healing or 0,tonumber(tag[2].value) or 4)
        elseif kind=='regenerate' then p.regenerates=tonumber(tag[2].value) or 8
        elseif kind=='resistance' and tag[2].id=='steadfast' then p.steadfast=true
        elseif kind~='hides' then p.unsupported=true end
    end
    return p
end
function P.capture(data,config,expired)
    local side=wesnoth.current.side;local map=wesnoth.current.map
    data.public=data.public or {terrain={},owners={},last_seen={},homes={}}
    local memory=data.public;local codes={};local villages,castles,keeps={},{},{}
    for x=1,map.width do for y=1,map.height do
        if expired and expired() then return nil end
        local k=G.key(x,y)
        if not wesnoth.sides.is_shrouded(side,x,y) then memory.terrain[k]=map[{x,y}] end
        if memory.terrain[k] then codes[memory.terrain[k]]=true end
    end end
    for _,p in ipairs(wesnoth.map.find{gives_income=true}) do
        local k=G.key(p[1],p[2])
        if memory.terrain[k] then
            villages[k]={x=p[1],y=p[2]}
            if not wesnoth.sides.is_shrouded(side,p[1],p[2]) and not wesnoth.sides.is_fogged(side,p[1],p[2]) then
                memory.owners[k]=wesnoth.map.get_owner(p) or 0
            end
        end
    end
    for _,p in ipairs(wesnoth.map.find{terrain='C*,K*'}) do
        local k=G.key(p[1],p[2]);if memory.terrain[k] then castles[k]={x=p[1],y=p[2]} end
    end
    for _,p in ipairs(wesnoth.map.find{terrain='K*'}) do
        local k=G.key(p[1],p[2]);if memory.terrain[k] then keeps[k]={x=p[1],y=p[2]} end
    end
    local s={side=side,root_side=side,turn=wesnoth.current.turn,max_turns=wesnoth.scenario.turns,
        players=#wesnoth.sides,units={},enemies={},gold={[side]=wesnoth.sides[side].gold},
        terrain=G.copy(memory.terrain),owners=G.copy(memory.owners),villages=villages,castles=castles,keeps=keeps,
        adjustment={},bonuses={},homes=memory.homes,village_value=config.village_value or 14,
        outside_keep_gold=config.outside_keep_gold or 1}
    s.lawful_bonus=wesnoth.schedule.get_time_of_day(nil).lawful_bonus
    for turn=s.turn,math.min(s.max_turns,s.turn+2) do s.bonuses[turn]=wesnoth.schedule.get_time_of_day(nil,turn).lawful_bonus end
    local allied=0
    for a=1,s.players do s.enemies[a]={};for b=1,s.players do s.enemies[a][b]=wesnoth.sides.is_enemy(a,b) end end
    for a=1,s.players do if a~=side and not s.enemies[side][a] then allied=allied+1 end end
    s.ffa=s.players>2 and allied==0;s.format=s.players==2 and 'duel' or s.ffa and 'ffa4' or 'team2v2'
    local raw,visible={},{ }
    for _,u in ipairs(wesnoth.units.find_on_map{{'filter_vision',{side=side,visible='yes'}}}) do visible[u.id]=u end
    for _,u in ipairs(wesnoth.units.find_on_map{side=side}) do visible[u.id]=u end
    for id,u in pairs(visible) do
        if expired and expired() then return nil end
        local p=P.profile(u,codes);s.units[id]=p;raw[id]=u
        if u.side==side and u.canrecruit and not memory.homes[id] then memory.homes[id]={x=u.x,y=u.y} end
        if s.enemies[side][u.side] then memory.last_seen[id]={x=u.x,y=u.y,turn=s.turn,side=u.side} end
    end
    for id,p in pairs(memory.last_seen) do
        if not visible[id] and not wesnoth.sides.is_fogged(side,p.x,p.y) and not wesnoth.sides.is_shrouded(side,p.x,p.y) then
            memory.last_seen[id]=nil
        end
    end
    s.sightings=memory.last_seen;s.recruits={}
    for _,name in ipairs(wesnoth.sides[side].recruit) do
        if expired and expired() then return nil end
        if wesnoth.unit_types[name].cost<=s.gold[side] then
            local u=wesnoth.units.create{type=name,side=side,random_traits=false,random_gender=false,
                generate_name=false,id='search_template_'..name,underlying_id=2147483647}
            s.recruits[#s.recruits+1]=P.profile(u,codes)
        end
    end
    return s,raw
end
return P
