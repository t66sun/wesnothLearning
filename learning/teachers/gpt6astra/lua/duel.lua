local AH = wesnoth.require 'ai/lua/ai_helper.lua'
local V = wesnoth.require '~add-ons/gpt6astra/lua/value.lua'
local M = {}
local players = #wesnoth.sides
local attack_risk = players==2 and 0.35 or players==8 and 0.9 or 0.65
local death_cost = players==2 and 0.7 or players==8 and 1.8 or 1.1
local advance_risk = players==2 and 0.25 or players==8 and 0.95 or 0.55
local leader_pressure = players==2 and 2.5 or players==8 and 0.5 or 1.5
local function key(x,y) return x*1000+y end
local function dist(a,b) return wesnoth.map.distance_between(a.x or a[1],a.y or a[2],b.x or b[1],b.y or b[2]) end
local function terrain(x,y) return wesnoth.current.map[{x,y}] end
local function value(u) return (u.cost or wesnoth.unit_types[u.type].cost)*(1+0.35*u.experience/math.max(1,u.max_experience)) end
local function tod(u,turn)
    -- shortcut: standard contest schedule; query scenario schedules before supporting custom scenarios.
    local b=({0,0.25,0.25,0,-0.25,-0.25})[(turn-1)%6+1]
    if u.alignment=='lawful' then return 1+b elseif u.alignment=='chaotic' then return 1-b elseif u.alignment=='liminal' then return 1-math.abs(b) end
    return 1
end
local weights={
    ['Drake Burner']=1.0,['Drake Clasher']=1.4,['Drake Fighter']=1.8,['Drake Glider']=0.25,['Saurian Augur']=1.2,['Saurian Skirmisher']=0.8,
    ['Dwarvish Fighter']=2.3,['Dwarvish Guardsman']=0.3,['Dwarvish Thunderer']=0.8,['Dwarvish Ulfserker']=0.25,Footpad=1.3,['Gryphon Rider']=0.3,Poacher=1.0,Thief=0.4,
    Bowman=0.8,Cavalryman=0.8,Fencer=0.2,['Heavy Infantryman']=0.4,Horseman=0.5,Mage=0.7,['Merman Fighter']=0.01,Spearman=3.8,
    ['Goblin Spearman']=0.3,['Naga Fighter']=0.01,['Orcish Archer']=0.7,['Orcish Assassin']=1.0,['Orcish Grunt']=4.0,['Troll Whelp']=1.4,['Wolf Rider']=0.4,
    ['Elvish Archer']=1.7,['Elvish Fighter']=2.8,['Elvish Scout']=0.25,['Elvish Shaman']=0.7,['Merman Hunter']=0.01,Wose=0.6,
    ['Dark Adept']=2.4,Ghost=0.65,Ghoul=0.65,Skeleton=2.2,['Skeleton Archer']=0.8,['Vampire Bat']=0.1,['Walking Corpse']=0.15,
}

local function context(data)
    local side=wesnoth.current.side
    local own=wesnoth.units.find_on_map{side=side}
    local enemies=AH.get_attackable_enemies()
    local occ={}
    for _,u in ipairs(own) do occ[key(u.x,u.y)]=u end
    for _,u in ipairs(enemies) do occ[key(u.x,u.y)]=u end
    data.owners=data.owners or {}
    data.home=data.home or {}
    local villages=wesnoth.map.find{gives_income=true}
    for _,p in ipairs(villages) do
        if not wesnoth.sides.is_fogged(side,p[1],p[2]) then data.owners[key(p[1],p[2])]=wesnoth.map.get_owner(p) or 0 end
    end
    local leaders={}
    for _,u in ipairs(own) do if u.canrecruit then
        leaders[#leaders+1]=u
        if not data.home[u.id] then data.home[u.id]={u.x,u.y} end
    end end
    return {side=side,own=own,enemies=enemies,occ=occ,villages=villages,leaders=leaders,turn=wesnoth.current.turn,
        home=leaders[1] and data.home[leaders[1].id], homes=data.home, multiplayer=#wesnoth.sides>2}
end

local function build_threat(c)
    local threats={}
    for _,e in ipairs(c.enemies) do
        local clone=e:clone();clone.moves=e.max_moves
        local seen={}
        for _,p in ipairs(wesnoth.paths.find_reach(clone,{viewing_side=c.side})) do
            for x,y in wesnoth.current.map:iter_adjacent(p[1],p[2]) do
                local k=key(x,y)
                if not seen[k] then
                    seen[k]=true
                    threats[k]=threats[k] or {};threats[k][#threats[k]+1]=e
                end
            end
        end
    end
    c.threats=threats
end

local function danger(c,u,x,y,excluded)
    local hits={}
    local dodge=u:defense_on(terrain(x,y))/100
    for _,e in ipairs(c.threats[key(x,y)] or {}) do if e.id~=excluded then
        local damage=0
        for _,a in ipairs(e.attacks) do
            damage=math.max(damage,a.damage*a.number*(1-dodge)*(1-u:resistance_against(a.type)/100)*tod(e,e.side>c.side and c.turn or c.turn+1))
        end
        damage=damage*V.DAMAGE_UPLIFT
        if e.status.slowed then damage=damage*V.SLOW_DAMAGE end
        hits[#hits+1]=damage*(0.7+0.3*e.hitpoints/e.max_hitpoints)
    end end
    table.sort(hits,function(a,b) return a>b end)
    local total=0
    for i=1,math.min(4,#hits) do total=total+hits[i]*(i==1 and 1 or 0.75) end
    return total,#hits
end

local function recruit(c,data)
    local gold=wesnoth.sides[c.side].gold
    local counts={};for _,u in ipairs(c.own) do if not u.canrecruit then counts[u.type]=(counts[u.type] or 0)+1 end end
    local names={}
    local undead,drakes=0,0
    for _,e in ipairs(c.enemies) do
        if e:resistance_against('blade')>=30 then undead=undead+1 end
        if e:resistance_against('fire')>=40 then drakes=drakes+1 end
    end
    for _,name in ipairs(wesnoth.sides[c.side].recruit) do
        if wesnoth.unit_types[name].cost<=gold then
            local w=weights[name] or 1
            if undead>1 and (name=='Mage' or name=='Dark Adept' or name=='Wose' or name=='Heavy Infantryman' or name=='Troll Whelp' or name=='Drake Burner') then w=w*2 end
            if drakes>1 and (name=='Spearman' or name=='Elvish Archer' or name=='Dark Adept' or name=='Saurian Skirmisher') then w=w*1.8 end
            names[#names+1]={name=name,score=w/(1+(counts[name] or 0))}
        end
    end
    table.sort(names,function(a,b) return a.score>b.score end)
    local slots={}
    for _,p in ipairs(wesnoth.map.find{terrain='C*,K*'}) do
        if not c.occ[key(p[1],p[2])] then
            local d=100
            for _,l in ipairs(c.leaders) do d=math.min(d,dist(l,p)) end
            if d<=3 then
                local enemy=100
                for _,e in ipairs(c.enemies) do enemy=math.min(enemy,dist(e,p)) end
                slots[#slots+1]={p=p,score=-enemy}
            end
        end
    end
    table.sort(slots,function(a,b) return a.score>b.score end)
    for _,n in ipairs(names) do for _,s in ipairs(slots) do
        if ai.check_recruit(n.name,s.p).ok then return {kind='recruit',type=n.name,x=s.p[1],y=s.p[2]} end
    end end
end

local function attacks(c,start)
    local best,score=nil,0.5
    local sims=0
    local pressure={}
    for _,e in ipairs(c.enemies) do if e.canrecruit then
        local damage=0
        for _,u in ipairs(c.own) do if u.attacks_left>0 and dist(u,e)<=u.moves+1 then
            local hit=0
            for _,a in ipairs(u.attacks) do hit=math.max(hit,a.damage*a.number*(1-e:resistance_against(a.type)/100)*tod(u,c.turn)*0.55) end
            damage=damage+hit
        end end
        pressure[e.id]=math.min(1,damage/math.max(1,e.hitpoints))
    end end
    for _,u in ipairs(c.own) do if u.attacks_left>0 then
        local reach={[key(u.x,u.y)]={u.x,u.y}}
        if u.moves>0 then for _,p in ipairs(wesnoth.paths.find_reach(u,{viewing_side=c.side})) do
            if not c.occ[key(p[1],p[2])] then reach[key(p[1],p[2])]=p end
        end end
        for _,e in ipairs(c.enemies) do
            if dist(u,e)<=u.moves+1 then
                for x,y in wesnoth.current.map:iter_adjacent(e.x,e.y) do if reach[key(x,y)] and
                    (not u.canrecruit or dist({x,y},c.homes[u.id])<=1 or e.canrecruit) then
                    local clone=u:clone();clone.x=x;clone.y=y
                    local risk=danger(c,u,x,y,e.id)
                    for weapon=1,#u.attacks do
                        local a,d=wesnoth.simulate_combat(clone,weapon,e)
                        sims=sims+1
                        local kill=d.hp_chance[0] or 0
                        local death=a.hp_chance[0] or 0
                        local dealt=e.hitpoints-d.average_hp
                        local taken=u.hitpoints-a.average_hp
                        local uv,ev=value(u),value(e)
                        local s=V.combat_score{dealt=dealt,taken=taken,kill=kill,death=death,
                            enemy_value=ev,enemy_max=e.max_hitpoints,own_value=uv,own_max=u.max_hitpoints,
                            death_cost=death_cost,poison=d.poisoned or 0,enemy_poisoned=e.status.poisoned,
                            slow=d.slowed or 0,enemy_slowed=e.status.slowed,
                            own_poison=a.poisoned or 0,own_poisoned=u.status.poisoned,
                            risk=risk,expected_hp=a.average_hp,risk_weight=attack_risk}
                        if e.canrecruit then s=s+kill*(#wesnoth.sides==2 and 250 or 130)+dealt*(0.25+leader_pressure*(pressure[e.id] or 0)^3) end
                        if u.canrecruit then
                            s=s-death*500-math.max(0,risk-a.average_hp+18)*5
                            if dist({x,y},c.homes[u.id])>1 then s=s-30 end
                        end
                        if c.multiplayer and c.home then s=s-math.max(0,dist({x,y},c.home)-6)*1.2 end
                        if u.experience+8*math.max(1,e.level)>=u.max_experience then s=s+kill*uv*0.6 end
                        s=s+(u:defense_on(terrain(x,y))-40)*0.015
                        if s>score and (x==u.x and y==u.y or ai.check_move(u,x,y).ok) then
                            score=s;best={kind='combat',id=u.id,x=u.x,y=u.y,tx=x,ty=y,enemy=e.id,ex=e.x,ey=e.y,weapon=weapon}
                        end
                        if sims>=240 or wesnoth.ms_since_init()-start>350 then return best end
                    end
                end end
            end
        end
    end end
    return best
end

local function movement(c,data,start)
    local best,bscore=nil,-1e9
    local vmap={};for _,v in ipairs(c.villages) do vmap[key(v[1],v[2])]=true end
    for _,u in ipairs(c.own) do if u.moves>0 then
        local goals={}
        local hurt=u.hitpoints<u.max_hitpoints*0.65 or u.status.poisoned
        local home=data.home[u.id]
        if u.canrecruit then
            goals[#goals+1]={home[1],home[2],bonus=14}
            if c.turn==1 then for _,v in ipairs(c.villages) do
                if dist(u,v)<=2 and data.owners[key(v[1],v[2])]~=c.side then goals[#goals+1]={v[1],v[2],bonus=38} end
            end end
            if hurt then for _,v in ipairs(c.villages) do if dist(u,v)<=u.max_moves+1 then goals[#goals+1]={v[1],v[2],bonus=23} end end end
        else
            for _,v in ipairs(c.villages) do
                local owner=data.owners[key(v[1],v[2])]
                if owner~=c.side or hurt or c.multiplayer then
                    local occupied=c.occ[key(v[1],v[2])]
                    if not occupied or occupied.id==u.id then goals[#goals+1]={v[1],v[2],bonus=(hurt and 21 or owner==c.side and 8 or 13)+(owner and owner~=0 and owner~=c.side and 3 or 0)} end
                end
            end
            if not hurt then for _,e in ipairs(c.enemies) do goals[#goals+1]={e.x,e.y,bonus=e.canrecruit and 12 or 8} end end
            if #goals==0 then for _,p in ipairs(wesnoth.map.find{terrain='K*'}) do goals[#goals+1]={p[1],p[2],bonus=8} end end
        end
        local function rating(x,y)
            local risk,n=danger(c,u,x,y)
            local goal=-100
            for _,g in ipairs(goals) do goal=math.max(goal,g.bonus-dist({x,y},g)*2.5) end
            local def=u:defense_on(terrain(x,y))
            local support=0
            for _,friend in ipairs(c.own) do if friend.id~=u.id and dist({x,y},friend)<=2 then support=support+1 end end
            local risk_weight=u.canrecruit and 2.8 or (hurt and 1.5 or advance_risk)
            local s=goal+def*0.035-risk*risk_weight
            s=s-math.max(0,risk-u.hitpoints*0.7)*(u.canrecruit and 5 or 0.7)
            if n>0 and not u.canrecruit then s=s+math.min(support,4)*(c.multiplayer and 3 or 1.5) end
            if c.multiplayer and not u.canrecruit and c.home then s=s-math.max(0,dist({x,y},c.home)-6)*1.2 end
            if vmap[key(x,y)] then
                if data.owners[key(x,y)]~=c.side then s=s+7 end
                if u.hitpoints<u.max_hitpoints then s=s+math.min(8,u.max_hitpoints-u.hitpoints)*(hurt and 1.1 or 0.5) end
                if u.status.poisoned then s=s+12 end
            end
            if u.canrecruit and home and x==home[1] and y==home[2] then s=s+9 end
            return s
        end
        local current=rating(u.x,u.y)
        local uscore,up=current,nil
        for _,p in ipairs(wesnoth.paths.find_reach(u,{viewing_side=c.side})) do
            if not c.occ[key(p[1],p[2])] then
                local s=rating(p[1],p[2])
                if s>uscore+0.05 and ai.check_move(u,p[1],p[2]).ok then uscore=s;up=p end
            end
        end
        if up then
            local score=uscore-current+(u.canrecruit and 8 or 0)
            if score>bscore then bscore=score;best={kind='move',id=u.id,x=u.x,y=u.y,tx=up[1],ty=up[2]} end
        end
        if wesnoth.ms_since_init()-start>500 then break end
    end end
    return best
end

function M:evaluation(cfg,data)
    local start=wesnoth.ms_since_init()
    data.plan=nil
    local c=context(data)
    local a=recruit(c,data)
    if not a then
        build_threat(c)
        a=attacks(c,start)
        if not a then a=movement(c,data,start) end
    end
    data.plan=a
    return a and 100000 or 0
end

local function move(u,x,y,full)
    local path=wesnoth.paths.find_path(u,x,y,{viewing_side=wesnoth.current.side})
    assert(path and path[2], 'checked move has no next step')
    local seen={}
    for _,e in ipairs(AH.get_attackable_enemies()) do seen[e.id]=true end
    local started=wesnoth.ms_since_init()
    for i=2,#path do
        local next_hex=path[i]
        if u.moves<=0 or not ai.check_move(u,next_hex[1],next_hex[2]).ok then return false end
        local final_step=i==#path
        assert((full and final_step and ai.move_full or ai.move)(u,next_hex).ok)
        if u.x==x and u.y==y then return true end
        for _,e in ipairs(AH.get_attackable_enemies()) do if not seen[e.id] then return false end end
        if wesnoth.ms_since_init()-started>150 then return false end
    end
    return false
end

function M:execution(cfg,data)
    local a=assert(data.plan)
    if a.kind=='recruit' then assert(ai.recruit(a.type,{a.x,a.y}).ok);return end
    local u=wesnoth.units.find_on_map{side=wesnoth.current.side,id=a.id}[1]
    if not u then return end
    if a.kind=='move' then
        if ai.check_move(u,a.tx,a.ty).ok then move(u,a.tx,a.ty,true) end
    else
        if u.x~=a.tx or u.y~=a.ty then
            if not ai.check_move(u,a.tx,a.ty).ok or not move(u,a.tx,a.ty,false) then return end
        end
        for _,e in ipairs(AH.get_attackable_enemies()) do if e.id==a.enemy and ai.check_attack(u,e,a.weapon).ok then
            assert(ai.attack(u,e,a.weapon).ok);return
        end end
    end
end
return M
