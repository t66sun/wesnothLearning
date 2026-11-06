local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local S=wesnoth.require '~add-ons/search_teacher/lua/state.lua'
local C=wesnoth.require '~add-ons/search_teacher/lua/combat.lua'
local A={}
local weights={Spearman=3.8,['Orcish Grunt']=3.5,['Elvish Fighter']=2.8,['Elvish Archer']=1.5,
    ['Elvish Shaman']=.9,['Dark Adept']=2.4,Skeleton=2.2,['Dwarvish Fighter']=2.3,
    ['Drake Fighter']=1.8,['Drake Clasher']=1.4,['Saurian Augur']=1.2,Mage=.8}
function A.key(a) return table.concat({a.kind,a.id or a.type or '',a.tx or a.x or 0,a.ty or a.y or 0,a.enemy or '',a.weapon or 0},':') end
local function ordered(t)
    local result={};for _,v in pairs(t) do result[#result+1]=v end
    table.sort(result,function(a,b) return (a.id or G.key(a.x,a.y))<(b.id or G.key(b.x,b.y)) end);return result
end
local function threat(s,u,x,y)
    local total=0;local here={x=x,y=y}
    for _,e in pairs(s.units) do if e.hp>0 and s.enemies[u.side][e.side] and G.distance(e,here)<=e.max_moves+1 then
        local hit=0
        for _,w in ipairs(e.weapons) do
            local t=G.copy(u);t.x=x;t.y=y
            hit=math.max(hit,C.damage(s,e,t,w,true,w.charge)*w.number*C.chance(s,e,t,w,nil,true)*(e.slow and .5 or 1))
        end
        total=total+hit*math.max(.2,1-G.distance(e,here)/(e.max_moves+2))
    end end
    return total
end
local function position(s,u,x,y)
    local k=G.key(x,y);local value=(u.defense[s.terrain[k]] or 40)*.035
    local here={x=x,y=y};local nearest=99
    for _,v in pairs(s.villages) do
        local owner=s.owners[G.key(v.x,v.y)] or 0
        if owner==0 or s.enemies[u.side][owner] then nearest=math.min(nearest,G.distance(here,v)) end
    end
    value=value-math.min(20,nearest)*.85
    if s.villages[k] then
        if not s.owners[k] or s.owners[k]==0 or s.enemies[u.side][s.owners[k]] then value=value+13 end
        value=value+math.min(8,u.max_hp-u.hp)*u.cost/u.max_hp+(u.poison and 8 or 0)
    end
    local enemy=99
    for _,e in pairs(s.units) do if e.hp>0 and s.enemies[u.side][e.side] then enemy=math.min(enemy,G.distance(here,e)) end end
    if enemy==99 then for _,p in pairs(s.keeps) do enemy=math.min(enemy,G.distance(here,p)) end end
    if not u.leader then value=value-math.min(20,enemy)*.4 end
    local danger=threat(s,u,x,y)
    value=value-danger*(u.leader and .8 or .15)-math.max(0,danger-u.hp+6)*(u.leader and 5 or .8)
    if u.leader and s.homes[u.id] then value=value-G.distance(here,s.homes[u.id])*.8 end
    if u.regenerates then value=value+math.min(u.regenerates,u.max_hp-u.hp)*.3 end
    return value
end
function A.generate(s,config,expired,root)
    local result={};local occ=S.occupancy(s);local count=0
    local function add(a) a.key=A.key(a);result[#result+1]=a end
    local units=ordered(s.units)
    for _,u in ipairs(units) do if u.side==s.side and u.hp>0 and not u.petrified then
        if expired() then break end
        local reachable=S.reach(s,u,false,expired);local positions={}
        for _,p in pairs(reachable) do positions[#positions+1]=p end
        table.sort(positions,function(a,b) return G.key(a[1],a[2])<G.key(b[1],b[2]) end)
        if u.attacks_left>0 then
            for _,e in ipairs(units) do if e.hp>0 and not e.petrified and s.enemies[u.side][e.side] then
                for _,p in ipairs(G.neighbors(e.x,e.y)) do
                    local r=reachable[G.key(p[1],p[2])]
                    if r then for weapon=1,#u.weapons do
                        if expired() then break end
                        local attacker=G.copy(u);attacker.x=p[1];attacker.y=p[2]
                        local f=C.forecast(s,attacker,e,weapon);count=count+1
                        local risk=threat(s,attacker,p[1],p[2])
                        local score=(e.hp-f.dh)*e.cost/e.max_hp+f.kill*(e.cost*.8+(e.leader and 500 or 0))
                            -(u.hp-f.ah)*u.cost/u.max_hp-f.death*(u.cost*.8+(u.leader and 500 or 0))
                            +(not e.slow and f.slow*7 or 0)+(not e.poison and f.poison*8*e.cost/e.max_hp or 0)
                            -math.max(0,risk*(config.risk or .35)-f.ah+6)*u.cost/u.max_hp
                        add{kind='combat',id=u.id,x=u.x,y=u.y,tx=p[1],ty=p[2],remaining=r[3],enemy=e.id,
                            ex=e.x,ey=e.y,weapon=weapon,score=score}
                    end end
                end
            end end
        end
        if u.moves>0 and not config.attacks_only then
            local before=position(s,u,u.x,u.y);local moves={}
            for _,p in ipairs(positions) do if p[1]~=u.x or p[2]~=u.y then
                if expired() then break end
                local score=position(s,u,p[1],p[2])-before
                moves[#moves+1]={kind='move',id=u.id,x=u.x,y=u.y,tx=p[1],ty=p[2],remaining=0,score=score}
            end end
            table.sort(moves,function(a,b) if a.score==b.score then return A.key(a)<A.key(b) end;return a.score>b.score end)
            for i=1,math.min(2,#moves) do if moves[i].score>.05 then add(moves[i]) end end
        end
    end end
    if not config.attacks_only and s.side==s.root_side and (s.gold[s.side] or 0)>0 then
        local connected={};local queue={}
        for _,u in ipairs(units) do if u.hp>0 and u.side==s.side and u.leader and s.keeps[G.key(u.x,u.y)] then
            connected[G.key(u.x,u.y)]=true;queue[#queue+1]={u.x,u.y}
        end end
        local i=1
        while i<=#queue do local p=queue[i];i=i+1
            if expired() then break end
            for _,n in ipairs(G.neighbors(p[1],p[2])) do local k=G.key(n[1],n[2])
                if s.castles[k] and not connected[k] then connected[k]=true;queue[#queue+1]=n end
            end
        end
        local army=0;for _,u in ipairs(units) do if u.hp>0 and u.side==s.side then army=army+1 end end
        for _,u in ipairs(s.recruits) do if u.cost<=s.gold[s.side] then
            if expired() then break end
            local best,score=nil,-math.huge
            for _,p in ipairs(queue) do if not occ[G.key(p[1],p[2])] then
                if expired() then break end
                local value=position(s,u,p[1],p[2]);if value>score then best=p;score=value end
            end end
            if best then add{kind='recruit',type=u.type,x=best[1],y=best[2],recruit=u,
                score=4+math.log(weights[u.type] or .45)*2+math.max(0,9-army)*1.2+score*.1} end
        end end
    end
    add{kind='end_turn',score=0}
    table.sort(result,function(a,b) if a.score==b.score then return a.key<b.key end;return a.score>b.score end)
    while #result>(root and (config.root_width or 18) or (config.width or 6)) do table.remove(result) end
    return result,count
end
return A
