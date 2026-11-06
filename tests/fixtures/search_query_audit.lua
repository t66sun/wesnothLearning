-- Referee-side test instrumentation only; never included in a delivered teacher.
local teacher=wesnoth.dofile '~add-ons/search_teacher/lua/implementation.lua'
local public=wesnoth.require '~add-ons/search_teacher/lua/public.lua'
local config=wesnoth.require '~add-ons/search_teacher/lua/config.lua'
local options=wesnoth.require '~add-ons/search_teacher/lua/audit_options.lua'
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M={}
local function encode(value)
    if type(value)~='table' then return type(value)..':'..tostring(value) end
    local keys={};for k in pairs(value) do keys[#keys+1]=k end
    table.sort(keys,function(a,b) return type(a)..tostring(a)<type(b)..tostring(b) end)
    local result={};for _,k in ipairs(keys) do result[#result+1]=encode(k)..'='..encode(value[k]) end
    return '{'..table.concat(result,';')..'}'
end
local function snapshot()
    local result={turn=wesnoth.current.turn,side=wesnoth.current.side,units={},gold={},map={}}
    for _,u in ipairs(wesnoth.units.find_on_map{}) do result.units[u.id]=wml.tostring(u.__cfg) end
    for side,s in ipairs(wesnoth.sides) do result.gold[side]=s.gold end
    local map=wesnoth.current.map
    for x=1,map.width do for y=1,map.height do result.map[x*1000+y]=map[{x,y}] end end
    return encode(result)
end
function M:evaluation(cfg,data) return data.done and 0 or 100000 end
function M:execution(cfg,data)
    wesnoth.units.to_map{type='Spearman',id='audit_actor',side=1,x=3,y=3,random_traits=false}
    wesnoth.units.to_map{type='Orcish Grunt',id='audit_target',side=2,x=3,y=4,random_traits=false}
    wesnoth.units.to_map{type='Orcish Grunt',id='audit_hidden',side=2,x=14,y=13,random_traits=false}
    local seen={}
    for _,u in ipairs(wesnoth.units.find_on_map{{'filter_vision',{side=1,visible='yes'}}}) do seen[u.id]=true end
    assert(seen.audit_target and not seen.audit_hidden,'audit visibility setup failed')
    assert(wesnoth.sides.is_shrouded(1,15,15),'audit terrain must be unexplored')
    if options.hidden_variant then
        wesnoth.units.find_on_map{id='audit_hidden'}[1].hitpoints=1
        wesnoth.current.map[{15,15}]='Wo'
        for _=1,7 do mathx.random(1,1000000000) end
    end
    local before=snapshot();local observed=encode(public.capture({},config));local planned;local searches={}
    for _=1,options.queries do
        local memory={};teacher:evaluation({},memory);planned=encode(memory.plan)
        local search=assert(memory.search,'missing completed search diagnostics')
        assert(search.algorithm==config.algorithm and search.nodes>0 and search.depth>0,'search did not complete')
        if config.algorithm=='uct' then assert(search.root_covered and search.simulations>0 and search.sampled_combats>0,'no sampled combat') end
        searches[#searches+1]={algorithm=search.algorithm,nodes=search.nodes,depth=search.depth,
            simulations=search.simulations,sampled_combats=search.sampled_combats}
    end
    assert(before==snapshot(),'teacher query mutated the real battlefield')
    local successor=wesnoth.units.create{type='Spearman',side=1,random_traits=false,
        random_gender=false,generate_name=false}
    local draws={};for _=1,16 do draws[#draws+1]=mathx.random(1,1000000000) end
    judge.emit('SEARCH_QUERY_AUDIT',{unchanged=true,public=observed,plan=planned,
        successor_id=successor.id,successor_underlying=successor.__cfg.underlying_id,draws=draws,searches=searches})
    data.done=true;judge.finish('turn_limit')
end
return M
