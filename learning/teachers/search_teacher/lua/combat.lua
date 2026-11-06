-- Local probability model. It never calls a live-game forecast or RNG.
local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local C={}
local function adjacent(a,b) return G.distance(a,b)==1 end
local function ally(s,a,b) return not s.enemies[a][b] end
local function bonus(s,u)
    local lawful=s.lawful_bonus or 0
    for _,v in pairs(s.units) do
        if v.hp>0 and v.illuminates and G.distance(u,v)<=1 then lawful=math.min(25,lawful+25);break end
    end
    if u.alignment=='chaotic' then lawful=-lawful
    elseif u.alignment=='liminal' then lawful=-math.abs(lawful)
    elseif u.alignment~='lawful' then lawful=0 end
    if u.fearless then lawful=math.max(0,lawful) end
    local leadership=0
    for _,v in pairs(s.units) do
        if v.hp>0 and v.leadership and ally(s,u.side,v.side) and adjacent(u,v) then
            leadership=math.max(leadership,25*math.max(0,v.level-u.level))
        end
    end
    return 100+lawful+leadership
end
local function flanked(s,a,d)
    local x=2*d.x-a.x
    local r=2*(d.y-math.floor((d.x-1)/2))-(a.y-math.floor((a.x-1)/2))
    local y=r+math.floor((x-1)/2)
    for _,u in pairs(s.units) do
        if u.hp>0 and not u.petrified and u.x==x and u.y==y and s.enemies[d.side][u.side] then return true end
    end
    return false
end
function C.damage(s,a,d,w,offense,charge)
    if not w then return 0 end
    local resistance=d.resistance[w.type] or 0
    if offense and d.steadfast and resistance>0 then resistance=math.min(50,2*resistance) end
    local multiplier=(charge and 2 or 1)*(w.backstab and offense and flanked(s,a,d) and 2 or 1)
    return math.max(1,math.floor(w.damage*bonus(s,a)*(100-resistance)*multiplier/10000+.5))
end
function C.chance(s,a,d,w,counter,offense)
    if not w then return 0 end
    local terrain=s.terrain[G.key(d.x,d.y)]
    local p=1-(d.defense[terrain] or 40)/100
    p=math.max(0,math.min(1,p+((w.accuracy or 0)-(counter and counter.parry or 0))/100))
    if w.magical then p=.7 elseif w.marksman and offense then p=math.max(.6,p) end
    return p
end
function C.counter(s,a,d,w)
    local best,score=nil,-math.huge
    for _,v in ipairs(d.weapons) do
        if v.range==w.range and (v.defense_weight or 1)>0 then
            local value=C.damage(s,d,a,v,false,w.charge)*v.number*C.chance(s,d,a,v,w,false)
            if v.slow and not a.slow then value=value+5 end
            if value>score then best,score=v,value end
        end
    end
    return best
end
local function append(out,lookup,row)
    local k=table.concat({row.ah,row.dh,row.as,row.ds,row.ap,row.dp},':')
    if lookup[k] then lookup[k].p=lookup[k].p+row.p
    else lookup[k]=row;out[#out+1]=row end
end
local function strike(rows,attack,w,damage,chance,a,d)
    local out,lookup={},{}
    for _,row in ipairs(rows) do
        if row.ah<=0 or row.dh<=0 then append(out,lookup,row)
        else
            if chance<1 then local miss=G.copy(row);miss.p=miss.p*(1-chance);append(out,lookup,miss) end
            if chance>0 then
                local hit=G.copy(row);hit.p=hit.p*chance
                local hp,slow,poison=attack and 'dh' or 'ah',attack and 'ds' or 'as',attack and 'dp' or 'ap'
                local selfhp,selfslow=attack and 'ah' or 'dh',attack and 'as' or 'ds'
                local target,actor=attack and d or a,attack and a or d
                local loss=math.min(hit[hp],hit[selfslow]==1 and math.ceil(damage/2) or damage)
                hit[hp]=hit[hp]-loss
                if w.drains and not target.undrainable then hit[selfhp]=math.min(actor.max_hp,hit[selfhp]+math.floor(loss/2)) end
                if hit[hp]>0 then
                    if w.slow then hit[slow]=1 end
                    if w.poison and not target.unpoisonable then hit[poison]=1 end
                end
                append(out,lookup,hit)
            end
        end
    end
    return out
end
function C.forecast(s,a,d,index)
    local w=assert(a.weapons[index]);local counter=C.counter(s,a,d,w)
    local ad=C.damage(s,a,d,w,true,w.charge)
    local dd=counter and C.damage(s,d,a,counter,false,w.charge) or 0
    local ac=C.chance(s,a,d,w,counter,true)
    local dc=counter and C.chance(s,d,a,counter,w,false) or 0
    local rows={{ah=a.hp,dh=d.hp,as=a.slow and 1 or 0,ds=d.slow and 1 or 0,
        ap=a.poison and 1 or 0,dp=d.poison and 1 or 0,p=1}}
    local an,dn=w.number,counter and counter.number or 0
    local first=counter and counter.firststrike and not w.firststrike
    for i=1,math.max(an,dn) do
        if first and i<=dn then rows=strike(rows,false,counter,dd,dc,a,d) end
        if i<=an then rows=strike(rows,true,w,ad,ac,a,d) end
        if not first and i<=dn then rows=strike(rows,false,counter,dd,dc,a,d) end
    end
    local f={states=rows,ah=0,dh=0,death=0,kill=0,slow=0,poison=0,own_slow=0,own_poison=0,
        supported=not (a.unsupported or d.unsupported or w.berserk or w.plague or
            (counter and (counter.berserk or counter.plague)) or
            a.xp+8*math.max(1,d.level)>=a.max_xp or d.xp+8*math.max(1,a.level)>=d.max_xp)}
    for _,r in ipairs(rows) do
        f.ah=f.ah+r.p*r.ah;f.dh=f.dh+r.p*r.dh
        f.death=f.death+(r.ah==0 and r.p or 0);f.kill=f.kill+(r.dh==0 and r.p or 0)
        if r.ah>0 then f.own_slow=f.own_slow+r.p*r.as;f.own_poison=f.own_poison+r.p*r.ap end
        if r.dh>0 then f.slow=f.slow+r.p*r.ds;f.poison=f.poison+r.p*r.dp end
    end
    return f
end
function C.outcome(f,rng)
    if rng then
        local p=rng();for _,r in ipairs(f.states) do p=p-r.p;if p<=0 then return r end end
        return f.states[#f.states]
    end
    -- Deterministic projection for beam/PVS. Probability losses remain in the value correction.
    return {ah=f.death>=.5 and 0 or math.max(1,math.floor(f.ah+.5)),
        dh=f.kill>=.5 and 0 or math.max(1,math.floor(f.dh+.5)),as=f.own_slow>=.5 and 1 or 0,
        ds=f.slow>=.5 and 1 or 0,ap=f.own_poison>=.5 and 1 or 0,dp=f.poison>=.5 and 1 or 0}
end
return C
