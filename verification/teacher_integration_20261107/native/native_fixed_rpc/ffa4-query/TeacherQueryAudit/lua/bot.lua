-- Referee-side fixed test. These snapshots and RNG draws never enter a teacher.
local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
local T=wesnoth.require '~add-ons/LearningSupport/lua/teacher.lua'
local options=wesnoth.require '~add-ons/TeacherQueryAudit/lua/options.lua'
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M={}
local function encode(value)
    if type(value)~='table' then return type(value)..':'..tostring(value) end
    local keys={};for key in pairs(value) do keys[#keys+1]=key end
    table.sort(keys,function(a,b) return type(a)..tostring(a)<type(b)..tostring(b) end)
    local result={};for _,key in ipairs(keys) do result[#result+1]=encode(key)..'='..encode(value[key]) end
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
    if options.hang then data.teacher_query_begin(.05,false);while true do end end
    wesnoth.units.to_map{type='Spearman',id='audit_actor',side=1,x=3,y=3,random_traits=false}
    wesnoth.units.to_map{type='Orcish Grunt',id='audit_target',side=2,x=3,y=4,random_traits=false}
    wesnoth.units.to_map{type='Orcish Grunt',id='audit_hidden',side=2,x=14,y=13,random_traits=false}
    wesnoth.units.find_on_map{id='audit_actor'}[1].moves=0
    wesnoth.units.find_on_map{id='audit_target'}[1].hitpoints=6
    local seen={}
    for _,u in ipairs(wesnoth.units.find_on_map{{'filter_vision',{side=1,visible='yes'}}}) do seen[u.id]=true end
    assert(seen.audit_target and not seen.audit_hidden,'audit visibility setup failed')
    assert(wesnoth.sides.is_shrouded(1,15,15),'audit terrain must be unexplored')
    if options.hidden then
        wesnoth.units.find_on_map{id='audit_hidden'}[1].hitpoints=1
        wesnoth.current.map[{15,15}]='Wo'
        for _=1,7 do mathx.random(1,1000000000) end
    end
    local obs=O.capture({});T.observe(data,obs)
    local public=encode{global=obs.global,opponents=obs.opponents,spatial=obs.spatial,ledger=data.teacher_ledger}
    local ledger=encode(data.teacher_ledger);local before=snapshot();local planned;local queries={}
    for _=1,options.queries do
        local plan,result=T.plan(data,data.training)
        assert(not result.error,result.error)
        planned=encode(plan);queries[#queries+1]=result
    end
    assert(before==snapshot(),'query mutated the real battlefield')
    assert(ledger==encode(data.teacher_ledger),'search mutated persistent public history')
    local successor=wesnoth.units.create{type='Spearman',side=1,random_traits=false,
        random_gender=false,generate_name=false}
    local draws={};for _=1,16 do draws[#draws+1]=mathx.random(1,1000000000) end
    judge.emit('INTEGRATED_QUERY_AUDIT',{unchanged=true,public=public,plan=planned,queries=queries,
        successor_id=successor.id,successor_underlying=successor.__cfg.underlying_id,draws=draws})
    data.done=true;judge.finish('turn_limit')
end
return M
