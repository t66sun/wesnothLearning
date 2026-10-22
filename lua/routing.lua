-- Public opening roster only. Persist in per-side CA data, never infer from living units.
local M={}
function M.select(memory)
    if memory.model_format then return memory.model_format end
    local active={}
    for i,s in ipairs(wesnoth.sides) do
        if s.controller~='null' then active[#active+1]=i end
    end
    local teams={}
    for _,side in ipairs(active) do
        local found=false
        for _,team in ipairs(teams) do
            if not wesnoth.sides.is_enemy(side,team[1]) then team[#team+1]=side;found=true;break end
        end
        if not found then teams[#teams+1]={side} end
    end
    -- Reject asymmetric or non-equivalence team graphs explicitly.
    for _,a in ipairs(active) do for _,b in ipairs(active) do
        assert(wesnoth.sides.is_enemy(a,b)==wesnoth.sides.is_enemy(b,a),'unsupported asymmetric teams')
    end end
    for _,team in ipairs(teams) do for _,a in ipairs(team) do for _,b in ipairs(team) do
        assert(not wesnoth.sides.is_enemy(a,b),'unsupported team relationships')
    end end end
    for i,a in ipairs(teams) do for j,b in ipairs(teams) do
        if i~=j then for _,x in ipairs(a) do for _,y in ipairs(b) do
            assert(wesnoth.sides.is_enemy(x,y),'unsupported non-transitive teams')
        end end end
    end end
    local fmt
    if #active==2 and #teams==2 then fmt='duel'
    elseif #active==4 and #teams==2 and #teams[1]==2 and #teams[2]==2 then fmt='team2v2'
    elseif #active>=3 and #teams==#active then fmt='ffa4'
    else error('NeuralArena: unsupported team structure ('..#active..' sides, '..#teams..' teams)') end
    memory.model_format=fmt
    return fmt
end
return M
