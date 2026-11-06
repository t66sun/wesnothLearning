-- Appended only to an in-memory copy of candidates.lua by the diagnostic.
-- Public obs, visibility-aware reach and ai.check_* are the only inputs.
local audit_mode='@MODE@'
local audit_generate=M.generate
local audit_select=Selection.select
local proposed
local function audit_key(a)
    local parts={}
    for _,key in ipairs {'kind','x','y','tx','ty','ex','ey','type','weapon','full'} do
        parts[#parts+1]=key..'='..tostring(a[key])
    end
    return table.concat(parts,'|')
end
Selection.select=function(pool)
    proposed={}
    for _,a in ipairs(pool) do
        local copy={};for key,value in pairs(a) do copy[key]=value end
        proposed[#proposed+1]=copy
    end
    return audit_select(pool)
end
function M.generate(obs)
    proposed={}
    local started=wesnoth.ms_since_init()
    local actions,timing=audit_generate(obs)
    local base_count=#actions
    local seen={};for _,a in ipairs(actions) do seen[audit_key(a)]=true end
    local counts={reaches=0,recruit_probes=0,attack_probes=0,move_probes=0,predictions=0}
    local threats={}
    -- This is a public possible-attack envelope, not an optimal opponent policy.
    for _,enemy in ipairs(obs.enemies) do
        local clone=enemy:clone();clone.moves=enemy.max_moves
        counts.reaches=counts.reaches+1
        for _,p in ipairs(wesnoth.paths.find_reach(clone,{viewing_side=obs.side,ignore_visibility=false})) do
            for x,y in wesnoth.current.map:iter_adjacent(p[1],p[2]) do threats[x..','..y]=true end
        end
    end
    local missing={}
    local function add(a,u,e)
        local key=audit_key(a)
        if not seen[key] then
            a._unit=u or a._unit;a._enemy=e or a._enemy
            missing[#missing+1]=a;seen[key]=true
        end
    end
    if audit_mode~='A' then for _,a in ipairs(proposed) do add(a) end end
    if audit_mode=='C' then
        local castles={}
        for _,p in pairs(obs.tiles) do if p.terrain:match('^[CK]') then castles[#castles+1]={p.x,p.y} end end
        table.sort(castles,function(a,b) return a[1]<b[1] or a[1]==b[1] and a[2]<b[2] end)
        for _,kind in ipairs(wesnoth.sides[obs.side].recruit) do
            if wesnoth.unit_types[kind].cost<=wesnoth.sides[obs.side].gold then
                for _,p in ipairs(castles) do
                    counts.recruit_probes=counts.recruit_probes+1
                    if ai.check_recruit(kind,p).ok then
                        local u=wesnoth.units.create {type=kind,side=obs.side,x=p[1],y=p[2],random_traits=false,
                            random_gender=false,generate_name=false,facing='ne',id='learning_probe',underlying_id=2147483647}
                        add({kind='recruit',type=kind,x=p[1],y=p[2]},u)
                    end
                end
            end
        end
        for _,u in ipairs(obs.own) do
            if u.attacks_left>0 then
                for _,enemy in ipairs(obs.enemies) do
                    if distance(u.x,u.y,enemy)==1 then
                        for weapon=1,#u.attacks do
                            counts.attack_probes=counts.attack_probes+1
                            if ai.check_attack(u,enemy,weapon).ok then
                                add({kind='attack',x=u.x,y=u.y,tx=enemy.x,ty=enemy.y,weapon=weapon},u,enemy)
                            end
                        end
                    end
                end
            end
            if u.moves>0 then
                counts.reaches=counts.reaches+1
                for _,p in ipairs(wesnoth.paths.find_reach(u,{viewing_side=obs.side,ignore_visibility=false})) do
                    if (p[1]~=u.x or p[2]~=u.y) and not obs.occupied[p[1]..','..p[2]] then
                        counts.move_probes=counts.move_probes+1
                        if ai.check_move(u,p[1],p[2]).ok then
                            for _,full in ipairs {true,false} do
                                if full or p[3]>0 then
                                    add({kind='move',x=u.x,y=u.y,tx=p[1],ty=p[2],full=full,
                                        used=full and u.moves or u.moves-p[3]},u)
                                end
                            end
                            -- These fixtures use no move-attacks: actors with
                            -- moves have attacks_left=0. No hypothetical combat
                            -- legality is inferred from geometry alone.
                        end
                    end
                end
            end
        end
    end
    for _,a in ipairs(missing) do
        local u,e=a._unit,a._enemy
        local villages={};for _,v in ipairs(obs.villages) do villages[#villages+1]=v end
        table.sort(villages,function(x,y)
            local dx,dy=distance(u.x,u.y,x),distance(u.x,u.y,y)
            return dx<dy or dx==dy and (x[1]<y[1] or x[1]==y[1] and x[2]<y[2])
        end)
        while #villages>WORK.entities do table.remove(villages) end
        a.features,a.rule=features(obs,a,u,e,obs.enemies,villages,obs.friends)
        if e then
            local clone=u:clone();if a.kind=='move_attack' then clone.x=a.tx;clone.y=a.ty end
            local ours,theirs=wesnoth.simulate_combat(clone,a.weapon,e)
            a.features[15]=math.max(-4,math.min(4,(e.hitpoints-theirs.average_hp)/50))
            a.features[16]=math.max(-4,math.min(4,(u.hitpoints-ours.average_hp)/50))
            a.features[17]=theirs.hp_chance[0] or 0;a.features[18]=ours.hp_chance[0] or 0;a.features[24]=1
            counts.predictions=counts.predictions+1
        end
        actions[#actions+1]=a
    end
    if #missing>0 then S.actions(obs,actions) end
    local properties={}
    for index,a in ipairs(actions) do
        local x,y=a.tx or a.x,a.ty or a.y
        if a.kind=='attack' then x,y=a.x,a.y end
        local on_village=false
        for _,v in ipairs(obs.villages) do if v[1]==x and v[2]==y then on_village=true end end
        properties[index]={outside_attack_reach=not threats[tostring(x)..','..tostring(y)],
            village=on_village,owner=x and obs.memory.villages[x..','..y] or nil}
        for key in pairs(a) do if tostring(key):sub(1,1)=='_' then a[key]=nil end end
        a.priority=nil
    end
    timing.audit={mode=audit_mode,retained=base_count,proposed=#proposed,added=#missing,
        calls=counts,properties=properties,ms=wesnoth.ms_since_init()-started}
    return actions,timing
end
