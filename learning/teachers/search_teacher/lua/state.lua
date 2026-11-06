local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local C=wesnoth.require '~add-ons/search_teacher/lua/combat.lua'
local H=wesnoth.require '~add-ons/search_teacher/lua/healing.lua'
local S={}
function S.clone(s)
    local out=G.copy(s);out.units={};out.owners=G.copy(s.owners);out.gold=G.copy(s.gold)
    out.adjustment=G.copy(s.adjustment or {})
    out.defeated=G.copy(s.defeated or {})
    for id,u in pairs(s.units) do out.units[id]=G.copy(u) end
    return out
end
local function eliminate(s,unit)
    if not unit.leader or unit.hp>0 then return end
    for _,u in pairs(s.units) do if u.side==unit.side and u.leader and u.hp>0 then return end end
    s.defeated[unit.side]=true;s.gold[unit.side]=0
    for _,u in pairs(s.units) do if u.side==unit.side then u.hp=0;u.moves=0;u.attacks_left=0 end end
end
function S.occupancy(s)
    local result={};for id,u in pairs(s.units) do if u.hp>0 then result[G.key(u.x,u.y)]=id end end;return result
end
function S.reach(s,u,full,expired)
    local occ=S.occupancy(s);local limit=full and u.max_moves or u.moves
    local found={[G.key(u.x,u.y)]={u.x,u.y,limit}};local queue={found[G.key(u.x,u.y)]};local head=1
    while head<=#queue do
        if expired and expired() then break end
        local p=queue[head];head=head+1
        if p[3]>0 then
            for _,n in ipairs(G.neighbors(p[1],p[2])) do
                local k=G.key(n[1],n[2]);local terrain=s.terrain[k]
                local blocker=occ[k] and s.units[occ[k]]
                local remaining=p[3]-(u.movement[terrain] or 99)*(u.slow and 2 or 1)
                if terrain and remaining>=0 and (not blocker or not s.enemies[u.side][blocker.side]) then
                    if not u.skirmisher then
                        for _,z in ipairs(G.neighbors(n[1],n[2])) do
                            local other=occ[G.key(z[1],z[2])];other=other and s.units[other]
                            if other and other.level>0 and not other.petrified and s.enemies[u.side][other.side] then remaining=0;break end
                        end
                    end
                    if not found[k] or remaining>found[k][3] then
                        local row={n[1],n[2],remaining};found[k]=row;queue[#queue+1]=row
                    end
                end
            end
        end
    end
    for k in pairs(found) do if occ[k] and occ[k]~=u.id then found[k]=nil end end
    return found
end
function S.apply(s,a,rng)
    local out=S.clone(s)
    if a.kind=='end_turn' then
        for _,u in pairs(out.units) do if u.side==out.side then u.slow=false end end
        out.side=out.side%out.players+1
        if out.side==1 then out.turn=out.turn+1 end
        out.lawful_bonus=(out.bonuses or {})[out.turn] or out.lawful_bonus
        for _,u in pairs(out.units) do if u.side==out.side and u.hp>0 then
            u.moves=u.max_moves;u.attacks_left=1
        end end
        H.start(out)
        return out
    end
    if a.kind=='recruit' then
        local u=G.copy(a.recruit);u.id='recruit:'..a.type..':'..G.key(a.x,a.y)
        u.x=a.x;u.y=a.y;u.moves=0;u.attacks_left=0;out.units[u.id]=u
        out.gold[u.side]=(out.gold[u.side] or 0)-u.cost
        return out
    end
    local u=assert(out.units[a.id]);u.x=a.tx;u.y=a.ty;u.moves=a.remaining or 0
    local k=G.key(u.x,u.y)
    if out.villages[k] and (not out.owners[k] or out.owners[k]==0 or out.enemies[u.side][out.owners[k]]) then
        out.owners[k]=u.side
    end
    if a.kind=='combat' then
        local d=assert(out.units[a.enemy]);local f=C.forecast(out,u,d,a.weapon);local r=C.outcome(f,rng)
        if not rng then
            local own=(f.ah-r.ah)*u.cost/u.max_hp-(f.death-(r.ah==0 and 1 or 0))*(u.cost*.8+(u.leader and 500 or 0))
            local enemy=(f.dh-r.dh)*d.cost/d.max_hp-(f.kill-(r.dh==0 and 1 or 0))*(d.cost*.8+(d.leader and 500 or 0))
            out.adjustment[u.side]=(out.adjustment[u.side] or 0)+own
            out.adjustment[d.side]=(out.adjustment[d.side] or 0)+enemy
        end
        out.adjustment[u.side]=(out.adjustment[u.side] or 0)-(a.exposure_penalty or 0)
        u.hp=r.ah;d.hp=r.dh;u.slow=r.as==1;d.slow=r.ds==1;u.poison=r.ap==1;d.poison=r.dp==1
        u.attacks_left=0;u.moves=0;out.leaf_only=not f.supported
        eliminate(out,u);eliminate(out,d)
    end
    return out
end
function S.material(s,side)
    if s.defeated and s.defeated[side] then return 0 end
    local value=s.gold[side] or 0
    local can_recruit=false
    for _,u in pairs(s.units) do
        if u.side==side and u.hp>0 and u.leader and s.keeps[G.key(u.x,u.y)] then can_recruit=true end
    end
    if not can_recruit then value=value*(s.outside_keep_gold or 1) end
    for _,u in pairs(s.units) do if u.side==side then
        if u.hp>0 then
            value=value+u.cost*(.8+u.hp/u.max_hp)+(u.leader and 500+u.hp*1.5 or 0)
            if u.slow then value=value-5 end
            if u.poison then value=value-8*u.cost/u.max_hp end
        end
    end end
    for k,owner in pairs(s.owners) do if owner==side then
        value=value+(s.village_value or 14)*math.min(1,math.max(0,s.max_turns-s.turn+1)/4)
    end end
    return value+(s.adjustment[side] or 0)
end
function S.value(s,side)
    local own,enemy,n=0,0,0
    for other=1,s.players do
        local v=S.material(s,other)
        if s.enemies[side][other] then enemy=enemy+v;n=n+1 else own=own+v end
    end
    return own-enemy/math.max(1,s.ffa and n or 1)
end
return S
