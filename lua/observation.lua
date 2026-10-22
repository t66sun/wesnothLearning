local schema = wesnoth.require '~add-ons/@ADDON@/lua/features.lua'
local M = {}
local S=wesnoth.require '~add-ons/@ADDON@/lua/spatial.lua'
function M.normalize(values, fields)
    local result={}
    for i,f in ipairs(fields) do
        result[i]=f[1]=='unit_type_index' and (values[f[1]] or 0) or math.max(-4,math.min(4,(values[f[1]] or 0)/f[2]))
    end
    return result
end
function M.composition(units,values,prefix)
    for _,u in ipairs(units) do
        local level=u.level or 1
        local fields={level==0 and 'level0' or level==1 and 'level1' or 'level2plus'}
        if u.max_moves>=7 then fields[#fields+1]='fast' end
        if u.hitpoints<u.max_hitpoints*.5 then fields[#fields+1]='injured' end
        local damage={}
        for _,a in ipairs(u.attacks) do if a.type then damage[a.type]=true end end
        for t in pairs(damage) do fields[#fields+1]='damage_'..t end
        for _,field in ipairs(fields) do local key=(prefix or '')..field;values[key]=(values[key] or 0)+1 end
    end
end
function M.visible(side,x,y)
    return not wesnoth.sides.is_fogged(side,x,y) and not wesnoth.sides.is_shrouded(side,x,y)
end
function M.capture(memory,viewing_side)
    local side=viewing_side or wesnoth.current.side
    memory.villages=memory.villages or {}; memory.seen=memory.seen or {}
    local own=wesnoth.units.find_on_map {side=side}
    -- The vision filter is part of the query. No hidden unit fields are consumed.
    local visible=wesnoth.units.find_on_map { {'filter_vision',{side=side,visible='yes'}} }
    table.sort(own,function(a,b) return a.id<b.id end)
    table.sort(visible,function(a,b) return a.id<b.id end)
    local enemies,friends,allies,occupied,leader={}, {}, {}, {}, nil
    for _,u in ipairs(visible) do
        occupied[u.x..','..u.y]=u
        if wesnoth.sides.is_enemy(side,u.side) and not u.status.petrified then
            enemies[#enemies+1]=u; memory.seen[u.side]=true
        elseif not wesnoth.sides.is_enemy(side,u.side) then
            friends[#friends+1]=u
            if u.side~=side then allies[#allies+1]=u end
        end
    end
    local hp=0
    for _,u in ipairs(own) do hp=hp+u.hitpoints;if u.canrecruit and not leader then leader=u end end
    if leader and not memory.home then memory.home={leader.x,leader.y} end
    local villages={}
    for _,p in ipairs(wesnoth.map.find {gives_income=true}) do
        if not wesnoth.sides.is_shrouded(side,p[1],p[2]) or memory.villages[p[1]..','..p[2]]~=nil then villages[#villages+1]=p end
    end
    table.sort(villages,function(a,b) return a[1]<b[1] or a[1]==b[1] and a[2]<b[2] end)
    local owned,counts=0,{}
    for _,p in ipairs(villages) do
        local key=p[1]..','..p[2]
        if M.visible(side,p[1],p[2]) then memory.villages[key]=wesnoth.map.get_owner(p) or 0 end
        local owner=memory.villages[key]
        if owner then counts[owner]=(counts[owner] or 0)+1 end
        if owner==side then owned=owned+1 end
    end
    local opponent_rows, initial,teammates={},0,0
    local threat=0
    if not memory.roster then
        memory.roster={}
        for i,s in ipairs(wesnoth.sides) do if s.controller~='null' then memory.roster[#memory.roster+1]=i end end
    end
    for _,i in ipairs(memory.roster) do
        if wesnoth.sides.is_enemy(side,i) then
            initial=initial+1
            local v={nearest_to_own_leader=50,known_villages=counts[i] or 0,
                ever_seen=memory.seen[i] and 1 or 0,alive_unknown=1}
            for _,u in ipairs(enemies) do
                if u.side==i then
                    v.visible_units=(v.visible_units or 0)+1
                    v.visible_hp=(v.visible_hp or 0)+u.hitpoints
                    v.visible_cost=(v.visible_cost or 0)+wesnoth.unit_types[u.type].cost
                    v.visible_leaders=(v.visible_leaders or 0)+(u.canrecruit and 1 or 0)
                    if leader then
                        local d=wesnoth.map.distance_between(leader.x,leader.y,u.x,u.y)
                        v.nearest_to_own_leader=math.min(v.nearest_to_own_leader,d)
                        if d<=u.max_moves+1 then threat=threat+1 end
                    end
                end
            end
            local army={}
            for _,u in ipairs(enemies) do if u.side==i then army[#army+1]=u end end
            M.composition(army,v)
            opponent_rows[#opponent_rows+1]=M.normalize(v,schema.opponent_features)
        elseif i~=side then teammates=teammates+1 end
    end
    local allied_hp,nearest=0,50
    for _,u in ipairs(allies) do
        allied_hp=allied_hp+u.hitpoints
        if leader and u.canrecruit then nearest=math.min(nearest,wesnoth.map.distance_between(leader.x,leader.y,u.x,u.y)) end
    end
    local s=wesnoth.sides[side]
    local values={initial_opponents=initial,size_duel=initial==1 and 1 or 0,
        size_medium=(initial>=2 and initial<=6) and 1 or 0,size_large=initial>=7 and 1 or 0,
        known_alive=0,alive_unknown=1,gold=s.gold,income=s.total_income or 0,
        own_units=#own,own_hp=hp,leader_hp_fraction=leader and leader.hitpoints/leader.max_hitpoints or 0,
        -- At 'time over', current.turn is already past the scenario limit.
        -- The native default reads that current schedule without validating a future-turn argument.
        leader_visible_threat=threat,lawful_bonus=wesnoth.schedule.get_time_of_day(nil).lawful_bonus,
        turn=wesnoth.current.turn,visible_enemies=#enemies,known_owned_villages=owned,
        teammates=teammates,visible_allied_units=#allies,visible_allied_hp=allied_hp,
        nearest_allied_leader=nearest,previous_end_turns=memory.end_turns or 0,repeated_moves=memory.repeated_moves or 0}
    M.composition(own,values,'own_');M.composition(enemies,values,'enemy_')
    for _,u in ipairs(own) do values.remaining_unit_moves=(values.remaining_unit_moves or 0)+u.moves end
    local material=0
    for _,u in ipairs(own) do material=material+wesnoth.unit_types[u.type].cost*u.hitpoints/u.max_hitpoints end
    -- A small, bounded training potential, using only the side's legal view.
    -- This is metadata; the frozen network input schema remains unchanged.
    local potential=math.min(1,owned*.04+material/1000+.2*values.leader_hp_fraction+allied_hp/10000)
    local global=M.normalize(values,schema.global_features)
    local obs={global=global,opponents=opponent_rows,own=own,enemies=enemies,leader=leader,
        occupied=occupied,villages=villages,memory=memory,side=side,friends=friends,potential=potential}
    S.capture(obs)
    return obs
end
return M
