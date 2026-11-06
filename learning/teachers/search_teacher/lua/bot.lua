local P=wesnoth.require '~add-ons/search_teacher/lua/public.lua'
local A=wesnoth.require '~add-ons/search_teacher/lua/actions.lua'
local Search=wesnoth.require '~add-ons/search_teacher/lua/search.lua'
local E=wesnoth.require '~add-ons/search_teacher/lua/execute.lua'
local config=wesnoth.require '~add-ons/search_teacher/lua/config.lua'
local M={}
function M:evaluation(cfg,data)
    local start=wesnoth.ms_since_init()
    data.plan=nil
    local function planning_expired() return wesnoth.ms_since_init()-start>=config.planning_ms end
    local state,raw=P.capture(data,config,planning_expired)
    if not state then data.search={ms=wesnoth.ms_since_init()-start,depth=0,expired=true};return 0 end
    local settings=config[state.format] or config
    local function expired() return wesnoth.ms_since_init()-start>=(settings.tactical_ms or 700) end
    local actions,predictions=A.generate(state,settings,expired,true)
    local legal={}
    for _,a in ipairs(actions) do
        local ok=a.kind=='end_turn' or a.kind=='recruit' and ai.check_recruit(a.type,{a.x,a.y}).ok
        if a.id then ok=(a.x==a.tx and a.y==a.ty or ai.check_move(raw[a.id],a.tx,a.ty).ok) end
        if ok then legal[#legal+1]=a end
    end
    if #legal==0 then data.plan=nil;return 0 end
    local action,stats=Search.choose(state,legal,settings,expired)
    stats.ms=wesnoth.ms_since_init()-start;stats.predictions=predictions;stats.algorithm=settings.algorithm
    stats.model='public-local-v1';data.search=stats
    stats.expired=stats.ms>=(settings.planning_ms or 1000)
    data.plan=action.kind~='end_turn' and action or nil
    return data.plan and 100000 or 0
end
function M:execution(cfg,data) E.run(data.plan) end
return M
