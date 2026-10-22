-- All inputs originate from O.capture's legal view. No true-state unit lookup.
local schema=wesnoth.require '~add-ons/@ADDON@/lua/features.lua'
local M={}
local types={};for i,t in ipairs(schema.unit_types) do types[t]=i-1 end
local terrains={};for i,t in ipairs(schema.terrain_types) do terrains[t]=(i-1)/math.max(1,#schema.terrain_types-1) end
local function norm(values,fields)
    local row={};for i,f in ipairs(fields) do row[i]=math.max(-4,math.min(4,(values[f[1]] or 0)/f[2])) end;return row
end
local function append(to,from) for _,v in ipairs(from) do to[#to+1]=v end end
local function dims() return wesnoth.current.map.width,wesnoth.current.map.height end
function M.entity(u,side,age)
    local w,h=dims()
    local v={x=u.x/w,y=u.y/h,hp=u.hitpoints,max_hp=u.max_hitpoints,moves=u.moves,max_moves=u.max_moves,
        attacks_left=u.attacks_left,experience=u.experience,max_experience=u.max_experience,level=u.level,
        leader=u.canrecruit and 1 or 0,own=u.side==side and 1 or 0,
        ally=u.side~=side and not wesnoth.sides.is_enemy(side,u.side) and 1 or 0,
        enemy=wesnoth.sides.is_enemy(side,u.side) and 1 or 0,age=age or 0}
    for _,s in ipairs {'poisoned','slowed','petrified'} do v[s]=u.status[s] and 1 or 0 end
    v['alignment_'..(u.alignment or 'neutral')]=1
    for _,t in ipairs(schema.damage_types) do v['resistance_'..t]=u:resistance_against(t) end
    for name,t in pairs(schema.terrains) do v['move_cost_'..name]=u:movement_on(t);v['terrain_defense_'..name]=u:defense_on(t) end
    for i=1,math.min(3,#u.attacks) do
        local a=u.attacks[i];local p='weapon'..i..'_'
        v[p..'damage']=a.damage;v[p..'strikes']=a.number;v[p..(a.range or 'melee')]=1;v[p..a.type]=1
        for _,tag in ipairs(a.__cfg or {}) do if tag[1]=='specials' then
            for _,s in ipairs(tag[2]) do v[p..(s[2].id or s[1])]=1 end
        end end
    end
    return {id=u.id,type_index=types[u.type] or 0,features=norm(v,schema.entity_features),
        x=u.x,y=u.y,side=u.side,turn=wesnoth.current.turn,leader=u.canrecruit or false}
end
function M.capture(obs)
    local w,h=dims();local mem=obs.memory
    mem.known_terrain=mem.known_terrain or {};mem.last_seen=mem.last_seen or {}
    local tiles,board={},{}
    for c=1,#schema.spatial_channels do board[c]={};for y=1,16 do board[c][y]={};for x=1,16 do board[c][y][x]=0 end end end
    for x=1,w do for y=1,h do
        local key=x..','..y
        local visible=not wesnoth.sides.is_fogged(obs.side,x,y) and not wesnoth.sides.is_shrouded(obs.side,x,y)
        if not wesnoth.sides.is_shrouded(obs.side,x,y) then mem.known_terrain[key]=wesnoth.current.map[{x,y}] end
        local terrain=mem.known_terrain[key]
        if terrain then
            local u=obs.occupied[key]
            local own=u and u.side==obs.side;local ally=u and not own and not wesnoth.sides.is_enemy(obs.side,u.side)
            local enemy=u and wesnoth.sides.is_enemy(obs.side,u.side)
            local row={1,visible and 1 or 0,own and u.hitpoints/100 or 0,ally and u.hitpoints/100 or 0,
                enemy and u.hitpoints/100 or 0,terrain:find('%^V') and 1 or 0,terrain:match('^[CK]') and 1 or 0,
                terrain:match('^[WS]') and 1 or 0,terrains[terrain] or 0}
            tiles[key]={x=x,y=y,terrain=terrain,channels=row,visible=visible,owner=mem.villages[key]}
            local bx=math.floor((x-1)*16/w)+1;local by=math.floor((y-1)*16/h)+1
            for c,v in ipairs(row) do board[c][by][bx]=board[c][by][bx]+v/(math.ceil(w/16)*math.ceil(h/16)) end
        end
    end end
    local entities,lookup={},{}
    for _,u in ipairs(obs.friends) do local e=M.entity(u,obs.side);lookup[e.id]=e;entities[#entities+1]=e end
    for _,u in ipairs(obs.enemies) do local e=M.entity(u,obs.side);lookup[e.id]=e;entities[#entities+1]=e;mem.last_seen[e.id]=e end
    for id,e in pairs(mem.last_seen) do
        if not lookup[id] then
            local tile=tiles[e.x..','..e.y]
            if tile and tile.visible then mem.last_seen[id]=nil
            else
                local copy={};for k,v in pairs(e) do copy[k]=v end
                copy.features={};for i,v in ipairs(e.features) do copy.features[i]=v end
                copy.features[18]=math.min(4,(wesnoth.current.turn-e.turn)/30)
                entities[#entities+1]=copy
            end
        end
    end
    table.sort(entities,function(a,b) if a.leader~=b.leader then return a.leader end;return a.id<b.id end)
    obs.spatial={board=board,entities=entities};obs.tiles=tiles;obs.entity_lookup=lookup
    return obs.spatial
end
function M.actions(obs,actions)
    local w,h=dims();local relevant={}
    local function describe(u)
        if not u then return nil end
        local e=obs.entity_lookup[u.id] or M.entity(u,obs.side);relevant[e.id]=true;return e
    end
    for _,a in ipairs(actions) do
        local actor=a._unit or obs.occupied[(a.x or 0)..','..(a.y or 0)]
        local target=a._enemy
        if not target and (a.kind=='attack' or a.kind=='move_attack') then
            target=obs.occupied[(a.ex or a.tx)..','..(a.ey or a.ty)]
        end
        a.actor=describe(actor);a.target=describe(target)
        local ax,ay=actor and actor.x or 0,actor and actor.y or 0
        local tx,ty=target and target.x or 0,target and target.y or 0
        local dx,dy=a.tx or a.x or 0,a.ty or a.y or 0
        if a.kind=='attack' then dx=ax;dy=ay end
        a.geometry={ax/w,ay/h,tx/w,ty/h,dx/w,dy/h,(dx-ax)/w,(dy-ay)/h,(tx-dx)/w,(ty-dy)/h,
            actor and wesnoth.map.distance_between(ax,ay,dx,dy)/math.max(w,h) or 0,
            target and wesnoth.map.distance_between(dx,dy,tx,ty)/math.max(w,h) or 0,
            actor and 1 or 0,target and 1 or 0,(a.weapon or 0)/3,a.full and 1 or 0}
        local q=dx-1;local r=dy-1-math.floor((q-(q%2))/2)
        a['local']={}
        for dq=-2,2 do for dr=math.max(-2,-dq-2),math.min(2,-dq+2) do
            local x=q+dq+1;local y=r+dr+math.floor(((q+dq)-((q+dq)%2))/2)+1
            local tile=obs.tiles[x..','..y]
            append(a['local'],tile and tile.channels or {0,0,0,0,0,0,0,0,0})
        end end
    end
    table.sort(obs.spatial.entities,function(a,b)
        local pa=(relevant[a.id] and 2 or 0)+(a.leader and 1 or 0)
        local pb=(relevant[b.id] and 2 or 0)+(b.leader and 1 or 0)
        return pa>pb or pa==pb and a.id<b.id
    end)
    while #obs.spatial.entities>128 do table.remove(obs.spatial.entities) end
end
function M.memory_observation(obs)
    M.actions(obs,{})
    return {global=obs.global,opponents=obs.opponents,spatial=obs.spatial,turn=wesnoth.current.turn,candidates={}}
end
return M
