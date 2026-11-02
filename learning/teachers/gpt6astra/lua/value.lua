-- Shared tactical values for probabilistic_combat_v2 rules.
-- Native half-damage slow and eight-point poison; retain the teacher decision
-- structure while evaluating the engine's public combat probabilities.
local V={}

V.COMBAT_PROFILE='probabilistic_combat_v2'
V.DAMAGE_UPLIFT=1.0
V.SLOW_DAMAGE=0.5
V.POISON_TICK=8
V.SLOW_MOVE_VALUE=2

function V.poison_gain(value,max_hp)
    return V.POISON_TICK*(value or 0)/math.max(1,max_hp or 1)
end

function V.slow_gain(risk)
    return (1-V.SLOW_DAMAGE)*(risk or 0)+V.SLOW_MOVE_VALUE
end

function V.combat_score(p)
    local ev,uv=p.enemy_value or 0,p.own_value or 0
    local emax,umax=math.max(1,p.enemy_max or 1),math.max(1,p.own_max or 1)
    local s=(p.dealt or 0)*ev/emax+(p.kill or 0)*ev*0.8
        -(p.taken or 0)*uv/umax-(p.death or 0)*uv*(p.death_cost or 0.7)
    if not p.enemy_poisoned then s=s+(p.poison or 0)*V.poison_gain(ev,emax) end
    if not p.enemy_slowed then s=s+(p.slow or 0)*V.slow_gain(p.risk) end
    if not p.own_poisoned then s=s-(p.own_poison or 0)*V.poison_gain(uv,umax) end
    s=s-math.max(0,(p.risk or 0)*(p.risk_weight or 0.35)-(p.expected_hp or 0)+6)*uv/umax*1.3
    return s
end

return V
