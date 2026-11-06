local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local A=wesnoth.require '~add-ons/search_teacher/lua/actions.lua'
local Monte=wesnoth.require '~add-ons/search_teacher/lua/monte_search.lua'
local H={}
function H.choose(state,actions,config,expired,beam)
    local champion,stats=beam(state,actions,config,expired)
    stats.algorithm='hybrid';stats.beam_depth=stats.depth;stats.beam_value=stats.value
    stats.hybrid_replaced=false;stats.simulations=0;stats.sampled_combats=0
    if expired() or champion.kind~='combat' or stats.depth==0 then return champion,stats end
    local roots={champion};local limit=math.max(2,config.mc_width or 4)
    local ending={kind='end_turn',score=0};ending.key=A.key(ending)
    for _,action in ipairs(actions) do
        if action.kind=='end_turn' then ending=action
        elseif action.kind=='combat' and action.key~=champion.key and #roots<limit-1 then
            roots[#roots+1]=action
        end
    end
    roots[#roots+1]=ending
    local cfg=G.copy(config);cfg.mc_width=#roots
    local choice,mc=Monte.choose(state,roots,cfg,expired)
    stats.nodes=stats.nodes+mc.nodes;stats.simulations=mc.simulations;stats.sampled_combats=mc.sampled_combats
    stats.root_visits=mc.root_visits;stats.root_values=mc.root_values;stats.root_covered=mc.root_covered
    stats.mc_depth=mc.depth;stats.utility=mc.utility
    local eligible=mc.root_covered
    for _,action in ipairs(roots) do
        if (mc.root_visits[action.key] or 0)<(config.hybrid_min_visits or 3) then eligible=false end
    end
    if eligible then
        stats.hybrid_utility_delta=mc.root_values[choice.key]-mc.root_values[champion.key]
        if stats.hybrid_utility_delta>(config.hybrid_margin or .02) then
            champion=choice;stats.hybrid_replaced=true;stats.value=nil
        end
    end
    return champion,stats
end
return H
