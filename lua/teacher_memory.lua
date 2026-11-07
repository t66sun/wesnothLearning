-- Independent per-seat public history. No search state is committed here.
local M={}
local function key(coordinate)
    local x,y=coordinate:match('^(%d+),(%d+)$')
    return tonumber(x)*1000+tonumber(y)
end
function M.observe(data,obs)
    data.owners=data.owners or {};data.home=data.home or {}
    data.public=data.public or {terrain={},owners={},last_seen={},homes={}}
    local public=data.public
    for key,owner in pairs(obs.memory.villages or {}) do
        local x,y=key:match('^(%d+),(%d+)$');local position=tonumber(x)*1000+tonumber(y)
        data.owners[position]=owner;public.owners[position]=owner
    end
    for coordinate,tile in pairs(obs.tiles or {}) do public.terrain[key(coordinate)]=tile.terrain end
    for _,u in ipairs(obs.own) do
        if not data.home[u.id] then data.home[u.id]={u.x,u.y} end
        if u.canrecruit and not public.homes[u.id] then public.homes[u.id]={x=u.x,y=u.y} end
    end
    -- Student execution also captures a legal post-action observation. Preserve
    -- those sightings if they are hidden again before the next teacher query.
    for id,seen in pairs(obs.memory.last_seen or {}) do
        public.last_seen[id]={x=seen.x,y=seen.y,turn=seen.turn,side=seen.side}
    end
    local visible={}
    for _,u in pairs(obs.occupied) do
        visible[u.id]=true
        if wesnoth.sides.is_enemy(obs.side,u.side) then
            public.last_seen[u.id]={x=u.x,y=u.y,turn=wesnoth.current.turn,side=u.side}
        end
    end
    for id,seen in pairs(public.last_seen) do
        local tile=(obs.tiles or {})[seen.x..','..seen.y]
        if not visible[id] and tile and tile.visible then public.last_seen[id]=nil end
    end
end
return M
