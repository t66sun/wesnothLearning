local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local T=wesnoth.require '~add-ons/search_teacher/lua/tree_model.lua'
local U=wesnoth.require '~add-ons/search_teacher/lua/uct.lua'
local M={}
function M.choose(state,actions,config,expired)
    local roots={};for i=1,math.min(#actions,config.mc_width or 8) do roots[i]=actions[i] end
    local root,model=T.create(state,roots,config,expired)
    local seed=config.search_seed or 9187;local identity=T.key(root)
    for i=1,#identity do seed=(seed*33+identity:byte(i))%2147483646 end
    return U.solve(root,model,config,expired,G.random(seed))
end
return M
