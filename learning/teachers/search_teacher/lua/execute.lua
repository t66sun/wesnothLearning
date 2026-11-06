local E={}
local function visible()
    return wesnoth.units.find_on_map{{'filter_vision',{side=wesnoth.current.side,visible='yes'}}}
end
local function move(u,x,y,full)
    local path=wesnoth.paths.find_path(u,x,y,{viewing_side=wesnoth.current.side})
    if not path or not path[2] then return false end
    local seen={};for _,e in ipairs(visible()) do seen[e.id]=true end
    local started=wesnoth.ms_since_init()
    for i=2,#path do
        local p=path[i]
        if u.moves<=0 or not ai.check_move(u,p[1],p[2]).ok then return false end
        local result=(full and i==#path and ai.move_full or ai.move)(u,p)
        if result.status==2005 or result.status==2006 then return false end
        assert(result.ok)
        -- New information invalidates a planned follow-up attack even at the destination.
        for _,e in ipairs(visible()) do if not seen[e.id] then return false end end
        if u.x==x and u.y==y then return true end
        if wesnoth.ms_since_init()-started>150 then return false end
    end
    return false
end
function E.run(a)
    if not a or a.kind=='end_turn' then return end
    if a.kind=='recruit' then assert(ai.recruit(a.type,{a.x,a.y}).ok);return end
    local u=wesnoth.units.find_on_map{side=wesnoth.current.side,id=a.id}[1]
    if not u then return end
    if a.kind=='move' then
        if ai.check_move(u,a.tx,a.ty).ok then move(u,a.tx,a.ty,true) end
    else
        if u.x~=a.tx or u.y~=a.ty then
            if not ai.check_move(u,a.tx,a.ty).ok or not move(u,a.tx,a.ty,false) then return end
        end
        for _,e in ipairs(visible()) do if e.id==a.enemy and ai.check_attack(u,e,a.weapon).ok then
            assert(ai.attack(u,e,a.weapon).ok);return
        end end
    end
end
return E
