-- The observer scores zero: it can never act, only publish the pre-action DTO.
local capture=wesnoth.require '~add-ons/LearningSupport/lua/stock_rca_capture/main.lua'
local M={}
function M:evaluation(cfg,data)
    if not data.probed then
        local functions={}
        for name,value in pairs(ai) do if type(value)=='function' then functions[#functions+1]=name end end
        table.sort(functions)
        capture.capabilities(functions,type(ai.teacher_turn)=='function' or type(ai.play_turn)=='function')
        data.probed=true
        -- Takeover needs a supported per-turn or per-decision query hook; record
        -- the actual runtime answer instead of assuming one.
        for _,name in ipairs {'teacher_turn','play_turn','take_turn'} do
            local present=type(ai[name])=='function'
            local detail=''
            if present then
                local ok,res=pcall(ai[name],{})
                present=ok
                detail=ok and 'callable with an empty observation' or tostring(res)
            end
            capture.hook(name,present,detail)
        end
    end
    data.memory=data.memory or {}
    capture.context(capture.row(data.memory),data.memory)
    return 0
end
function M:execution() error('zero-score stock observer must never execute') end
return M
