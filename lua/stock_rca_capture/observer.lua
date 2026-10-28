-- A zero-score observer runs before stock CAs, never executes an action.
local capture=wesnoth.require '~add-ons/LearningSupport/lua/stock_rca_capture/main.lua'
local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
local C=wesnoth.require '~add-ons/LearningSupport/lua/candidates.lua'
local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
local schema=wesnoth.require '~add-ons/LearningSupport/lua/features.lua'
local routing=wesnoth.require '~add-ons/LearningSupport/lua/routing.lua'
local M={}
function M:evaluation(cfg,data)
    if not data.probed then
        local functions={}
        for name,value in pairs(ai) do if type(value)=='function' then functions[#functions+1]=name end end
        table.sort(functions)
        capture.capabilities(functions,type(ai.teacher_turn)=='function' or type(ai.play_turn)=='function')
        data.probed=true
    end
    data.memory=data.memory or {}
    local obs=O.capture(data.memory)
    local candidates,timing=C.generate(obs,200)
    capture.context({schema=schema.version,global=obs.global,opponents=obs.opponents,
        spatial=obs.spatial,candidates=candidates,timing=timing,side=obs.side,
        turn=wesnoth.current.turn,format=routing.select(data.memory),version='stock-events-v1',
        memory_write=S.memory_observation(obs)},data.memory)
    return 0
end
function M:execution() error('zero-score stock observer must never execute') end
return M
