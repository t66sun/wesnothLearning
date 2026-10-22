local O=wesnoth.require '~add-ons/@ADDON@/lua/observation.lua'
local schema=wesnoth.require '~add-ons/@ADDON@/lua/features.lua'
local M={}
local S=wesnoth.require '~add-ons/@ADDON@/lua/spatial.lua'
local unit_index={}
for i,name in ipairs(schema.unit_types) do unit_index[name]=i-1 end
local function owner_kind(obs,p)
    local owner=obs.memory.villages[p[1]..','..p[2]]
    if owner==nil then return 'unknown' end
    if owner==0 then return 'neutral' end
    if owner==obs.side then return 'own' end
    return wesnoth.sides.is_enemy(obs.side,owner) and 'enemy' or 'ally'
end
local function unit_features(u,f)
    f.unit_type_index=unit_index[u.type] or 0
    f.max_hp=u.max_hitpoints;f.max_moves=u.max_moves;f.unit_level=u.level or 1
    f['alignment_'..(u.alignment or 'neutral')]=1
    for _,t in ipairs(schema.damage_types) do
        if u.resistance_against then f['resistance_'..t]=u:resistance_against(t) end
    end
    for name,terrain in pairs(schema.terrains) do
        if u.movement_on then f['move_cost_'..name]=u:movement_on(terrain) end
        f['terrain_defense_'..name]=u:defense_on(terrain)
    end
    for i=1,math.min(3,#u.attacks) do
        local a=u.attacks[i];local p='weapon'..i..'_'
        f[p..'damage']=a.damage or 0;f[p..'strikes']=a.number or 0
        f[p..(a.range or 'melee')]=1
        if a.type then f[p..a.type]=1 end
        local cfg=a.__cfg or {};local specials={}
        for _,child in ipairs(cfg) do
            if child[1]=='specials' then for _,v in ipairs(child[2]) do specials[v[2].id or v[1]]=true end end
        end
        for _,s in ipairs(schema.weapon_specials) do f[p..s]=specials[s] and 1 or 0 end
    end
end
local function distance(x,y,u) return wesnoth.map.distance_between(x,y,u.x or u[1],u.y or u[2]) end
local function minimum(x,y,units)
    local d=50
    for _,u in ipairs(units) do d=math.min(d,distance(x,y,u)) end
    return d
end
-- Build a public-information threat map once. Candidate shortlisting must see
-- terrain/safety/support at every reachable hex, not just a few goal endpoints.
local function threat_map(obs,expired)
    local threats={}
    if type(wesnoth.current.map.iter_adjacent)~='function' then return threats end
    for _,e in ipairs(obs.enemies) do
        if expired() then break end
        local clone=e:clone();clone.moves=e.max_moves
        local seen={}
        for _,p in ipairs(wesnoth.paths.find_reach(clone,{viewing_side=obs.side,ignore_visibility=false})) do
            for x,y in wesnoth.current.map:iter_adjacent(p[1],p[2]) do
                local k=x..','..y
                if not seen[k] then
                    seen[k]=true;threats[k]=threats[k] or {};threats[k][#threats[k]+1]=e
                end
            end
        end
    end
    return threats
end
local function tactical_ratings(obs,u,destinations,threats)
    local hurt=u.hitpoints<u.max_hitpoints*.65 or u.status.poisoned
    local multiplayer=#wesnoth.sides>2
    local home=obs.memory.home
    local goals,vmap={},{}
    local function goal(x,y,bonus) goals[#goals+1]={x,y,bonus=bonus} end
    if u.canrecruit and home then goal(home[1],home[2],14) end
    for _,v in ipairs(obs.villages) do
        local k=v[1]..','..v[2];vmap[k]=true
        local owner=obs.memory.villages[k]
        if u.canrecruit then
            if wesnoth.current.turn==1 and distance(u.x,u.y,v)<=2 and owner~=obs.side then goal(v[1],v[2],38) end
            if hurt and distance(u.x,u.y,v)<=u.max_moves+1 then goal(v[1],v[2],23) end
        elseif not obs.occupied[k] or obs.occupied[k].id==u.id or
            (obs.occupied[k].side~=obs.side and not wesnoth.sides.is_enemy(obs.side,obs.occupied[k].side)) then
            -- An allied occupant blocks landing, not the strategic village goal.
            -- Reachable destinations below still exclude every occupied hex.
            if owner~=obs.side or hurt or multiplayer then
                goal(v[1],v[2],(hurt and 21 or owner==obs.side and 8 or 13)+(owner and owner~=0 and owner~=obs.side and 3 or 0))
            end
        end
    end
    if not u.canrecruit then
        if not hurt then for _,e in ipairs(obs.enemies) do goal(e.x,e.y,e.canrecruit and 12 or 8) end end
        if hurt and multiplayer then
            for _,f in ipairs(obs.own) do
                for _,tag in ipairs(f.__cfg or {}) do
                    if tag[1]=='abilities' then for _,ability in ipairs(tag[2]) do
                        if ability[1]=='heals' and f.id~=u.id then goal(f.x,f.y,18) end
                    end end
                end
            end
        end
        if #goals==0 then for _,p in pairs(obs.tiles) do if p.terrain:match('^K') then goal(p.x,p.y,8) end end end
    end
    local radius=6+math.max(0,#obs.own-7)*.75
    for _,d in ipairs(destinations) do
        local x,y=d.p[1],d.p[2];local tile=obs.tiles[x..','..y];local terrain=tile and tile.terrain or 'Gg'
        local defense=u:defense_on(terrain);local hits={}
        for _,e in ipairs(threats[x..','..y] or {}) do
            local damage=0
            for _,a in ipairs(e.attacks) do
                local chance=1-defense/100;local multiplier=1
                if multiplayer then
                    for _,tag in ipairs(a.__cfg or {}) do
                        if tag[1]=='specials' then for _,s in ipairs(tag[2]) do
                            local id=s[2].id
                            if id=='magical' then chance=.7 elseif id=='marksman' then chance=math.max(.6,chance) end
                            if id=='charge' then multiplier=multiplier*1.7 end
                            if s[1]=='berserk' then multiplier=multiplier*2.5 end
                        end end
                    end
                    if e.status.slowed then multiplier=multiplier*.5 end
                end
                local turn=wesnoth.current.turn+(e.side>obs.side and 0 or 1)
                local bonus=({0,.25,.25,0,-.25,-.25})[(turn-1)%6+1]
                local tod=e.alignment=='lawful' and 1+bonus or e.alignment=='chaotic' and 1-bonus
                    or e.alignment=='liminal' and 1-math.abs(bonus) or 1
                local resistance=u.resistance_against and u:resistance_against(a.type) or 0
                damage=math.max(damage,(a.damage or 0)*(a.number or 0)*chance*(1-resistance/100)*tod*multiplier)
            end
            hits[#hits+1]=damage*(.7+.3*e.hitpoints/e.max_hitpoints)
        end
        table.sort(hits,function(a,b) return a>b end)
        local risk=0;for i=1,math.min(4,#hits) do risk=risk+hits[i]*(i==1 and 1 or .75) end
        local utility=-100
        for _,g in ipairs(goals) do utility=math.max(utility,g.bonus-distance(x,y,g)*2.5) end
        local support=0
        for _,f in ipairs(obs.own) do if f.id~=u.id and distance(x,y,f)<=2 then support=support+1 end end
        utility=utility+defense*.035-math.max(0,risk-u.hitpoints*.7)*(u.canrecruit and 5 or .7)
        if #hits>0 and not u.canrecruit then utility=utility+math.min(support,4)*(multiplayer and 3 or 1.5) end
        if multiplayer and not u.canrecruit and home then utility=utility-math.max(0,distance(x,y,home)-radius)*1.2 end
        if vmap[x..','..y] then
            if obs.memory.villages[x..','..y]~=obs.side then utility=utility+7 end
            utility=utility+math.min(8,u.max_hitpoints-u.hitpoints)*(hurt and 1.1 or .5)+(u.status.poisoned and 12 or 0)
            if multiplayer and not u.canrecruit and u.hitpoints>u.max_hitpoints*.8 then
                for _,f in ipairs(obs.own) do
                    if f.id~=u.id and f.hitpoints<f.max_hitpoints*.65 and distance(x,y,f)<=3 then
                        utility=utility-(f.canrecruit and 18 or 9);break
                    end
                end
            end
        end
        if home and x==home[1] and y==home[2] then utility=utility+(u.canrecruit and 9 or multiplayer and -15 or 0) end
        local risk_weight=u.canrecruit and 2.8 or hurt and 1.5 or multiplayer and .55 or .25
        d.tactical=utility-risk*risk_weight
        d.safe=utility-risk*(risk_weight+.5)
        d.advance=utility-risk*math.max(0,risk_weight-.2)
    end
end
local function features(obs,a,u,target)
    local f={[a.kind]=1}
    if not u then return O.normalize(f,schema.action_features),-1 end
    obs.unit_features=obs.unit_features or {}
    local unit_key=u.id..':'..u.type
    if not obs.unit_features[unit_key] then local v={};unit_features(u,v);obs.unit_features[unit_key]=v end
    for k,v in pairs(obs.unit_features[unit_key]) do f[k]=v end
    local x,y=a.tx or a.x,a.ty or a.y
    if a.kind=='attack' then x=u.x;y=u.y end
    f.unit_hp_fraction=u.hitpoints/u.max_hitpoints
    f.unit_cost=wesnoth.unit_types[u.type].cost
    f.own_leader=u.canrecruit and 1 or 0
    f.gold_cost=a.kind=='recruit' and f.unit_cost or 0
    f.movement_used=a.used or 0
    f.remaining_moves=a.full and 0 or math.max(0,u.moves-f.movement_used)
    f.enemy_approach=minimum(u.x,u.y,obs.enemies)-minimum(x,y,obs.enemies)
    f.defense=obs.tiles[x..','..y] and u:defense_on(obs.tiles[x..','..y].terrain) or 0
    f.visible_threat=0; f.friendly_support=0
    for _,e in ipairs(obs.enemies) do if distance(x,y,e)<=e.max_moves+1 then f.visible_threat=f.visible_threat+1 end end
    for _,v in ipairs(obs.friends) do if v.id~=u.id and distance(x,y,v)<=2 then f.friendly_support=f.friendly_support+1 end end
    local targets={}
    for _,p in ipairs(obs.villages) do
        local ownership=owner_kind(obs,p)
        if ownership~='own' and ownership~='ally' then targets[#targets+1]=p end
        if p[1]==x and p[2]==y then
            f.village_gain=(ownership~='own' and ownership~='ally') and 1 or 0
            f['village_'..ownership]=1
            f.healing=math.min(8,u.max_hitpoints-u.hitpoints)
        end
    end
    if a.goal_x then f.goal_progress=distance(u.x,u.y,{a.goal_x,a.goal_y})-distance(x,y,{a.goal_x,a.goal_y}) end
    local last=obs.memory.last_move and obs.memory.last_move[u.id]
    f.repeated_move=last and last.x==x and last.y==y and 1 or 0
    f.village_approach=minimum(u.x,u.y,targets)-minimum(x,y,targets)
    if target then f.target_leader=target.canrecruit and 1 or 0 end
    local score=(f.village_gain or 0)*6+f.village_approach*.4+f.enemy_approach*.15
        +(f.healing or 0)*.3+f.friendly_support*.1-f.visible_threat*(u.canrecruit and 1 or .15)
    if a.kind=='recruit' then score=4 end
    if target then score=score+2 end
    return O.normalize(f,schema.action_features),score
end
function M.generate(obs,budget_ms)
    local started=wesnoth.ms_since_init()
    local cut=false
    local work=0
    local function expired() work=work+1;if work>20000 then cut=true;return true end;return false end
    local actions={{kind='end_turn',features=O.normalize({end_turn=1},schema.action_features),rule=-1}}
    if not obs.leader then S.actions(obs,actions);return actions,{truncated=false,ms=wesnoth.ms_since_init()-started,predictions=0,work=work,budget='fixed-20000-v2'} end
    local pool={};local serial=0
    local function add(a,u,e)
        -- Features are comparatively expensive; only materialize retained slots.
        a.rule=a.priority or (a.kind=='recruit' and 4 or a.kind=='move' and 0 or 2)
        serial=serial+1;a._serial=serial;a._unit=u;a._enemy=e
        a._home=u.canrecruit and obs.memory.home and a.tx==obs.memory.home[1] and a.ty==obs.memory.home[2] or false
        pool[#pool+1]=a
    end
    local threats=threat_map(obs,expired)
    local castles={}
    for _,p in pairs(obs.tiles) do if p.terrain:match('^[CK]') then castles[#castles+1]={p.x,p.y} end end
    table.sort(castles,function(a,b) return a[1]<b[1] or a[1]==b[1] and a[2]<b[2] end)
    for _,name in ipairs(wesnoth.sides[obs.side].recruit) do
        if expired() then break end
        if wesnoth.unit_types[name].cost<=wesnoth.sides[obs.side].gold then
            local recruit_locations=0
            for _,p in ipairs(castles) do
                if expired() then break end
                if not obs.occupied[p[1]..','..p[2]] and ai.check_recruit(name,p).ok then
                    -- Explicit detached identity prevents probes consuming native unit IDs.
                    local u=wesnoth.units.create {type=name,side=obs.side,x=p[1],y=p[2],random_traits=false,
                        random_gender=false,generate_name=false,id='learning_probe',underlying_id=2147483647}
                    add({kind='recruit',type=name,x=p[1],y=p[2]},u)
                    recruit_locations=recruit_locations+1
                    if recruit_locations>=8 then break end
                end
            end
        end
    end
    for _,u in ipairs(obs.own) do
        if expired() then break end
        if u.attacks_left>0 then
            for _,e in ipairs(obs.enemies) do
                if distance(u.x,u.y,e)==1 then
                    for wi=1,#u.attacks do
                        if ai.check_attack(u,e,wi).ok then
                            add({kind='attack',x=u.x,y=u.y,tx=e.x,ty=e.y,weapon=wi},u,e)
                        end
                    end
                end
            end
        end
        if u.moves>0 then
            local reach=wesnoth.paths.find_reach(u,{viewing_side=obs.side,ignore_visibility=false})
            local destinations={}
            for _,p in ipairs(reach) do
                if expired() then break end
                if (p[1]~=u.x or p[2]~=u.y) and not obs.occupied[p[1]..','..p[2]] then
                    local score=-minimum(p[1],p[2],obs.enemies)*.2-minimum(p[1],p[2],obs.villages)
                    for _,e in ipairs(obs.enemies) do if distance(p[1],p[2],e)==1 then score=score+10 end end
                    destinations[#destinations+1]={p=p,score=score}
                end
            end
            -- Keep independent goal categories. Long-distance targets are reduced to
            -- a reachable point along their visibility-aware path this turn.
            local picked={};local selected={}
            local reachable={}
            for _,d in ipairs(destinations) do reachable[d.p[1]..','..d.p[2]]=d end
            local function pick(d,category,goal)
                if not d then return end
                local key=d.p[1]..','..d.p[2]
                if not picked[key] then
                    d.category=category;d.goal=goal;selected[#selected+1]=d;picked[key]=true
                elseif goal and not d.goal then
                    d.goal=goal
                end
            end
            local function best(category,score,goal)
                local winner,value
                for _,d in ipairs(destinations) do
                    local v=score(d.p)
                    if not winner or v>value or (v==value and (d.p[1]<winner.p[1] or d.p[1]==winner.p[1] and d.p[2]<winner.p[2])) then winner=d;value=v end
                end
                pick(winner,category,goal)
            end
            tactical_ratings(obs,u,destinations,threats)
            -- Several independent risk profiles, plus adjacent alternatives.
            -- No teacher plan/action is read here, in training or deployment.
            for _,profile in ipairs {'tactical','safe','advance'} do
                table.sort(destinations,function(a,b)
                    return a[profile]>b[profile] or a[profile]==b[profile] and (a.p[1]<b.p[1] or a.p[1]==b.p[1] and a.p[2]<b.p[2])
                end)
                for i=1,math.min(4,#destinations) do pick(destinations[i],'position') end
            end
            local goals={}
            for _,v in ipairs(obs.villages) do
                pick(reachable[v[1]..','..v[2]],'village',v)
                local k=owner_kind(obs,v)
                if k~='own' and k~='ally' then goals[#goals+1]=v end
            end
            table.sort(goals,function(a,b) local da=distance(u.x,u.y,a);local db=distance(u.x,u.y,b);return da<db or da==db and (a[1]<b[1] or a[1]==b[1] and a[2]<b[2]) end)
            for gi=1,math.min(3,#goals) do
                if expired() then break end
                local goal=goals[gi];local path
                if wesnoth.paths.find_path then path=wesnoth.paths.find_path(u,goal[1],goal[2],{viewing_side=obs.side,ignore_visibility=false}) end
                local positions={}
                for pi,p in ipairs(path or {}) do positions[p[1]..','..p[2]]=pi end
                -- Intermediate points expose where a safe path can be stopped by
                -- new vision; these are generated without a teacher answer.
                for _,p in ipairs(path or {}) do pick(reachable[p[1]..','..p[2]],'advance',goal) end
                best(gi==1 and 'village' or 'advance',function(p)
                    return positions[p[1]..','..p[2]] or -distance(p[1],p[2],goal)
                end,goal)
            end
            if u.canrecruit and obs.memory.home then
                local home=obs.memory.home
                if wesnoth.paths.find_path then
                    local path=wesnoth.paths.find_path(u,home[1],home[2],{viewing_side=obs.side,ignore_visibility=false})
                    for _,p in ipairs(path or {}) do pick(reachable[p[1]..','..p[2]],'return',home) end
                end
            end
            for _,d in ipairs(destinations) do
                for _,enemy in ipairs(obs.enemies) do
                    if distance(d.p[1],d.p[2],enemy)==1 then pick(d,'attack');break end
                end
            end
            best('attack',function(p) return -minimum(p[1],p[2],obs.enemies) end)
            best('retreat',function(p) return minimum(p[1],p[2],obs.enemies)+(p[3] or 0)*.01 end)
            best('heal',function(p)
                local on=false;for _,v in ipairs(obs.villages) do if v[1]==p[1] and v[2]==p[2] then on=true end end
                return (on and 100 or 0)-minimum(p[1],p[2],obs.villages)
            end)
            best('explore',function(p)
                return not O.visible(obs.side,p[1],p[2]) and 100-distance(u.x,u.y,p) or distance(u.x,u.y,p)
            end)
            local primary_move=true
            for _,d in ipairs(selected) do
                if expired() then break end
                local p=d.p
                if ai.check_move(u,p[1],p[2]).ok then
                    for _,full in ipairs {true,false} do
                        if full or (p[3] or 0)>0 then
                        add({kind='move',category=d.category,x=u.x,y=u.y,tx=p[1],ty=p[2],used=full and u.moves or u.moves-p[3],full=full,
                            _primary_move=full and primary_move,
                            priority=(d.category=='position' and 6 or 1)+(full and 0 or -20),
                            goal_x=d.goal and d.goal[1],goal_y=d.goal and d.goal[2]},u)
                        if full then primary_move=false end
                        end
                    end
                    if u.attacks_left>0 then
                        for _,e in ipairs(obs.enemies) do
                            if distance(p[1],p[2],e)==1 then
                                for wi=1,#u.attacks do
                                    add({kind='move_attack',x=u.x,y=u.y,tx=p[1],ty=p[2],ex=e.x,ey=e.y,
                                        weapon=wi,used=u.moves-p[3]},u,e)
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    table.sort(pool,function(a,b)
        if a._home~=b._home then return a._home end
        return a.rule>b.rule or a.rule==b.rule and a._serial<b._serial
    end)
    -- Reserve each unit's best legal full move before the shared 128-slot cap.
    -- Ratings use the public observation; no teacher plan enters this list.
    -- Fill remaining slots round-robin by unit/kind, full before stop variants.
    local groups,keys={},{}
    for _,a in ipairs(pool) do
        if a._primary_move then
            if #actions<128 then actions[#actions+1]=a end
        else
            local key=a.kind=='recruit' and 'recruit:'..a.type or a._unit.id..':'..(a.kind=='move' and 'move' or 'combat')
            if not groups[key] then groups[key]={};keys[#keys+1]=key end
            groups[key][#groups[key]+1]=a
        end
    end
    local index=1;local added=true
    while added and #actions<128 do
        added=false
        for _,key in ipairs(keys) do
            local a=groups[key][index]
            if a and #actions<128 then actions[#actions+1]=a;added=true end
        end
        index=index+1
    end
    if #pool>#actions-1 then cut=true end
    S.actions(obs,actions)
    local predictions=0
    for _,a in ipairs(actions) do
        if a._unit then a.features,a.rule=features(obs,a,a._unit,a._enemy) end
        if a._enemy and predictions<16 and not expired() then
            local clone=a._unit:clone()
            if a.kind=='move_attack' then clone.x=a.tx;clone.y=a.ty end
            local ours,theirs=wesnoth.simulate_combat(clone,a.weapon,a._enemy)
            a.features[15]=math.max(-4,math.min(4,(a._enemy.hitpoints-theirs.average_hp)/50))
            a.features[16]=math.max(-4,math.min(4,(clone.hitpoints-ours.average_hp)/50))
            a.features[17]=theirs.hp_chance[0] or 0; a.features[18]=ours.hp_chance[0] or 0
            a.features[24]=1
            a.rule=a.rule+a.features[15]*5-a.features[16]*6+a.features[17]*8-a.features[18]*10
            predictions=predictions+1
        end
        a._unit=nil;a._enemy=nil;a._serial=nil;a._home=nil;a._primary_move=nil;a.priority=nil
    end
    return actions,{truncated=cut,ms=wesnoth.ms_since_init()-started,predictions=predictions,work=work,budget='fixed-20000-v2'}
end
function M.diagnostics(obs,a)
    local moves=0;for _,u in ipairs(obs.own) do moves=moves+u.moves end
    local d={end_turn=a.kind=='end_turn',remaining_moves=moves,recruit_type=a.kind=='recruit' and a.type or nil,
        repeated_move=not not (a.features and a.features[#a.features-1]~=0),turn=wesnoth.current.turn}
    if a.kind=='move' or a.kind=='move_attack' then
        local terrain=wesnoth.current.map[{a.tx,a.ty}]
        d.left_castle=not string.match(terrain,'^[CK]')
        for _,p in ipairs(obs.villages) do if p[1]==a.tx and p[2]==a.ty then d.village_target=owner_kind(obs,p) end end
    end
    return d
end
function M.remember(obs,a)
    if a.kind=='end_turn' then obs.memory.end_turns=(obs.memory.end_turns or 0)+1 end
    if a.kind=='move' or a.kind=='move_attack' then
        local u=obs.occupied[a.x..','..a.y]
        if u then
            obs.memory.last_move=obs.memory.last_move or {}
            obs.memory.last_move[u.id]={x=a.x,y=a.y}
            local previous=a.features and a.features[#a.features-1]
            if previous and previous~=0 then obs.memory.repeated_moves=(obs.memory.repeated_moves or 0)+1 end
        end
    end
end
function M.outcome(a,diagnostics)
    if not diagnostics or not diagnostics.village_target then return end
    local u=wesnoth.units.get(a.tx,a.ty)
    diagnostics.village_captured=u and u.side==wesnoth.current.side
        and wesnoth.map.get_owner({a.tx,a.ty})==wesnoth.current.side
        and diagnostics.village_target~='own' and diagnostics.village_target~='ally' or false
end
function M.execute(a)
    if a.kind=='end_turn' then return {changed=true} end
    local result;local changed=false
    local function mark(r)
        if r and (r.gamestate_changed==true or r.ok and r.gamestate_changed~=false) then changed=true end
        return r
    end
    local function outcome(interrupted,u) return {changed=changed,interrupted=interrupted or false,x=u and u.x,y=u and u.y} end
    if a.kind=='recruit' then result=mark(ai.recruit(a.type,{a.x,a.y}))
    elseif a.kind=='attack' then result=mark(ai.attack({a.x,a.y},{a.tx,a.ty},a.weapon))
    else
        local u=wesnoth.units.get(a.x,a.y)
        if wesnoth.paths.atomic_path and u then
            -- The lite host accepts one atomic public path and applies its own
            -- interruption rules. Stepping through a public path would reject
            -- intermediate friendly-occupied tiles as illegal destinations.
            result=mark((a.full and ai.move_full or ai.move)(u,{a.tx,a.ty}))
        elseif wesnoth.paths.find_path and u then
            local path=wesnoth.paths.find_path(u,a.tx,a.ty,{viewing_side=wesnoth.current.side,ignore_visibility=false})
            local seen={}
            for _,v in ipairs(wesnoth.units.find_on_map { {'filter_vision',{side=wesnoth.current.side,visible='yes'}} }) do
                if wesnoth.sides.is_enemy(wesnoth.current.side,v.side) then seen[v.id]=true end
            end
            local started=wesnoth.ms_since_init()
            for i=2,#path do
                local p=path[i]
                if u.moves<=0 or not ai.check_move(u,p[1],p[2]).ok then return outcome(true,u) end
                result=mark((a.full and i==#path and ai.move_full or ai.move)(u,p))
                if result and not result.ok and result.gamestate_changed and (result.status==2005 or result.status==2006) then return outcome(true,u) end
                assert(result and result.ok,'movement rejected')
                local discovered=false
                for _,v in ipairs(wesnoth.units.find_on_map { {'filter_vision',{side=wesnoth.current.side,visible='yes'}} }) do
                    if wesnoth.sides.is_enemy(wesnoth.current.side,v.side) and not seen[v.id] then discovered=true end
                end
                if discovered or i>=64 then return outcome(true,u) end
            end
        else result=mark((a.full and ai.move_full or ai.move)({a.x,a.y},{a.tx,a.ty})) end
        -- 1.18.8 actions.hpp: ambush/failed teleport are normal hidden encounters.
        -- Stop the compound action and capture a fresh visible observation next call.
        if result and not result.ok and result.gamestate_changed and (result.status==2005 or result.status==2006) then return outcome(true,u) end
        assert(result.ok,'movement rejected: '..tostring(result.result))
        if a.kind=='move_attack' then
            local u=wesnoth.units.get(a.tx,a.ty)
            if u and u.side==wesnoth.current.side and ai.check_attack({a.tx,a.ty},{a.ex,a.ey},a.weapon).ok then
                result=mark(ai.attack({a.tx,a.ty},{a.ex,a.ey},a.weapon))
            end
        end
    end
    assert(result and result.ok,'native action rejected')
    return outcome(false)
end
return M
