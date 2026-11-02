-- Diagnostic wrapper: retain the teacher's real forecasts and scorer results.
local V=wesnoth.require '~add-ons/gpt6astra/lua/value.lua'
local M={}

local function probability(result)
    local hp={}
    for value,chance in pairs(result.hp_chance) do
        if chance~=0 then hp[tostring(value)]=chance end
    end
    return {average_hp=result.average_hp,hp_chance=hp,
        poisoned=result.poisoned,slowed=result.slowed}
end

function M:evaluation(cfg,data)
    local rows,last={}
    local simulate,score=wesnoth.simulate_combat,V.combat_score
    wesnoth.simulate_combat=function(attacker,weapon,defender)
        local a,d=simulate(attacker,weapon,defender)
        -- These fixed neutral, unslowed targets have ordinary melee weapons.
        -- At turn 1 the existing danger() TOD multiplier is exactly one.
        local target_damage=0
        local terrain=wesnoth.current.map[{attacker.x,attacker.y}]
        for _,w in ipairs(defender.attacks) do
            local damage=w.damage*w.number*(1-attacker:defense_on(terrain)/100)
                *(1-attacker:resistance_against(w.type)/100)
            target_damage=math.max(target_damage,damage)
        end
        last={weapon=weapon,attacker=attacker.id,defender=defender.id,
            forecast={attacker=probability(a),defender=probability(d)},
            target_damage_estimate=target_damage}
        return a,d
    end
    V.combat_score=function(p)
        local result=score(p)
        last.parameters=p;last.score=result
        rows[#rows+1]=last
        return result
    end
    local result=teacher:evaluation(cfg,data)
    wesnoth.simulate_combat,V.combat_score=simulate,score
    if data.plan then data.plan.score_trace=rows end
    return result
end

function M:execution(cfg,data) return teacher:execution(cfg,data) end
return M
