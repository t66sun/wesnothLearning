-- Fixed native decision, after the archived archer attack and before the shaman moves.
local folder = '~add-ons/ADDON/lua/'
local original = wesnoth.dofile(folder .. 'duel.lua')
local AH = wesnoth.require 'ai/lua/ai_helper.lua'
local judge = wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M = {}
local probe

function M:evaluation(cfg, data)
    if wesnoth.current.turn == 4 and wesnoth.current.side == 2 then
        local shaman = wesnoth.units.find_on_map {side=2, id='Elvish Shaman-14'}[1]
        if shaman and shaman.x == 20 and shaman.y == 20 and shaman.attacks_left > 0 then
            for _, enemy in ipairs(AH.get_attackable_enemies()) do
                if enemy.id == 'Cavalryman-8' and enemy.x == 21 and enemy.y == 18 and enemy.hitpoints == 14 then
                    probe = wesnoth.dofile(folder .. 'landing_probe_duel.lua')
                    local rating = probe:evaluation(cfg, data)
                    judge.emit('LANDING_DECISION', {plan=data.plan, rows=probe.landing_rows,
                        cutoff=probe.landing_cutoff, actor={x=shaman.x, y=shaman.y, hp=shaman.hitpoints,
                            moves=shaman.moves, attacks_left=shaman.attacks_left},
                        target={x=enemy.x, y=enemy.y, hp=enemy.hitpoints, max_hp=enemy.max_hitpoints},
                        village_legal=ai.check_move(shaman,21,19).ok,
                        grass_legal=ai.check_move(shaman,20,18).ok})
                    return rating
                end
            end
        end
    end
    return original:evaluation(cfg, data)
end

function M:execution(cfg, data)
    if probe then
        probe:execution(cfg, data)
        judge.finish('landing_diagnosis')
    else
        original:execution(cfg, data)
    end
end

return M