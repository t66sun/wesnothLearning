local P=wesnoth.require '~add-ons/search_teacher/lua/pvs.lua'
local T=wesnoth.require '~add-ons/search_teacher/lua/tree_model.lua'
local M={}
function M.choose(state,actions,config,expired)
    assert(not state.ffa,'PVS requires two opposed utilities')
    local root,model=T.create(state,actions,config,expired)
    local champion=actions[1];local cache,preferred={},{}
    local stats={depth=0,nodes=0,cutoffs=0,researches=0,cache_hits=0,algorithm='pvs'}
    for depth=1,config.tree_depth or 6 do
        local action,value,work=P.solve(root,model,depth,expired,cache,preferred)
        for _,key in ipairs{'nodes','cutoffs','researches','cache_hits'} do stats[key]=stats[key]+work[key] end
        if not action then break end
        champion=action;stats.depth=depth;stats.value=value/1000
    end
    return champion,stats
end
return M
