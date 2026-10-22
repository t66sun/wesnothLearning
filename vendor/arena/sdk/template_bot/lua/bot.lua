-- A small complete native AI. Replace the strategy; keep the CA entry points.
local AH = wesnoth.require 'ai/lua/ai_helper.lua'
local M = {}

function M:evaluation(cfg, data)
    data.plan = nil
    local side = wesnoth.current.side
    local own = wesnoth.units.find_on_map {side=side}
    table.sort(own,function(a,b) return a.id < b.id end)
    local enemies = AH.get_attackable_enemies()
    table.sort(enemies,function(a,b) return a.id < b.id end)
    for _, u in ipairs(own) do
        if u.attacks_left>0 then
            for _, e in ipairs(enemies) do
                if wesnoth.map.distance_between(u.x,u.y,e.x,e.y)==1 and ai.check_attack(u,e).ok then
                    data.plan={kind='attack', x=u.x,y=u.y,tx=e.x,ty=e.y}
                    return 100000
                end
            end
        end
    end
    local recruits = wesnoth.sides[side].recruit
    local castles = wesnoth.map.find {terrain='C*,K*'}
    for i=1,#recruits do
        local name = recruits[((#own+i-2)%#recruits)+1]
        if wesnoth.unit_types[name].cost<=wesnoth.sides[side].gold then
            for _, p in ipairs(castles) do
                if ai.check_recruit(name,p).ok then
                    data.plan={kind='recruit',type=name,x=p[1],y=p[2]}
                    return 100000
                end
            end
        end
    end
    local goals = {}
    for _, e in ipairs(enemies) do goals[#goals+1]={e.x,e.y} end
    for _, p in ipairs(wesnoth.map.find {gives_income=true}) do
        if wesnoth.map.get_owner(p)~=side then goals[#goals+1]=p end
    end
    local best, best_score
    for _, u in ipairs(own) do
        if u.moves>0 and not u.canrecruit then
            for _, p in ipairs(wesnoth.paths.find_reach(u)) do
                if (p[1]~=u.x or p[2]~=u.y) and not wesnoth.units.get(p[1],p[2]) then
                    local score = -100000
                    for _, goal in ipairs(goals) do
                        local d = wesnoth.map.distance_between(p[1],p[2],goal[1],goal[2])
                        local gain = wesnoth.map.distance_between(u.x,u.y,goal[1],goal[2])-d
                        score=math.max(score,gain*10-d)
                    end
                    if (not best_score or score>best_score) and ai.check_move(u,p[1],p[2]).ok then
                        best_score=score
                        best={kind='move',x=u.x,y=u.y,tx=p[1],ty=p[2]}
                    end
                end
            end
        end
    end
    if best and best_score>-100000 then data.plan=best;return 100000 end
    return 0
end

function M:execution(cfg, data)
    local a=data.plan
    assert(a,'evaluation must choose a plan')
    local result
    if a.kind=='attack' then result=ai.attack({a.x,a.y},{a.tx,a.ty})
    elseif a.kind=='recruit' then result=ai.recruit(a.type,{a.x,a.y})
    else result=ai.move_full({a.x,a.y},{a.tx,a.ty}) end
    assert(result.ok,'native action rejected: '..tostring(result.result))
end

return M
