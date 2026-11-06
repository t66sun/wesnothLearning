local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local S=wesnoth.require '~add-ons/search_teacher/lua/state.lua'
local A=wesnoth.require '~add-ons/search_teacher/lua/actions.lua'
local M={}
local function better(a,b)
    if a.value==b.value then return a.first.key<b.first.key end
    return a.value>b.value
end
function M.reply(s,config,expired)
    if s.leaf_only then return s end
    local out=s.side==s.root_side and S.apply(s,{kind='end_turn'}) or s
    local cfg=G.copy(config);cfg.attacks_only=true;cfg.width=config.reply_width or 3
    -- Each seat optimizes its own utility, including in FFA.
    for _=1,s.players-1 do
        if expired() then return nil end
        local reply_side=out.side
        for _=1,math.max(1,config.reply_actions or 1) do
            if expired() then return nil end
            local choices=A.generate(out,cfg,expired,false)
            local best,best_value=nil,-math.huge
            for _,a in ipairs(choices) do
                if expired() then return nil end
                local next_state=S.apply(out,a)
                local value=S.value(next_state,reply_side)
                if value>best_value then best,best_value=next_state,value end
            end
            out=best or out
            if out.leaf_only then return out end
            if out.side~=reply_side then break end
        end
        if out.side==reply_side then out=S.apply(out,{kind='end_turn'}) end
        if out.side==s.root_side then break end
    end
    return out
end
function M.beam(s,actions,config,expired)
    local fallback=actions[1];local champion=fallback;local best=-math.huge;local visited=0
    local base=S.value(s,s.root_side);local beam={}
    for _,a in ipairs(actions) do
        if expired() then return champion,{nodes=visited,depth=0} end
        local state=S.apply(s,a)
        local bonus=a.kind=='move' and a.score*(config.position_weight or .8) or 0
        beam[#beam+1]={state=state,first=a,value=S.value(state,s.root_side)-base+bonus,bonus=bonus,trace={a.key}}
        visited=visited+1
    end
    table.sort(beam,better)
    for depth=1,config.depth or 2 do
        local completed={}
        for _,node in ipairs(beam) do
            if expired() then return champion,{nodes=visited,depth=depth-1} end
            local reply=M.reply(node.state,config,expired)
            if not reply then return champion,{nodes=visited,depth=depth-1} end
            node.value=S.value(reply,s.root_side)-base+node.bonus
            completed[#completed+1]=node
        end
        table.sort(completed,better)
        beam=completed
        if completed[1] then champion=completed[1].first;best=completed[1].value end
        if depth==(config.depth or 2) then return champion,{nodes=visited,depth=depth,value=best} end
        local next_beam={}
        for i=1,math.min(config.width or 6,#beam) do
            local node=beam[i]
            if node.state.leaf_only or node.state.side~=s.root_side then next_beam[#next_beam+1]=node
            else
                if expired() then return champion,{nodes=visited,depth=depth,value=best} end
                local cfg=G.copy(config);cfg.attacks_only=true
                local choices=A.generate(node.state,cfg,expired,false)
                for _,a in ipairs(choices) do
                    if expired() then return champion,{nodes=visited,depth=depth,value=best} end
                    if a.kind=='end_turn' then next_beam[#next_beam+1]=node
                    else
                        local state=S.apply(node.state,a);local trace={table.unpack(node.trace)};trace[#trace+1]=a.key
                        next_beam[#next_beam+1]={state=state,first=node.first,bonus=node.bonus,trace=trace,
                            value=S.value(state,s.root_side)-base+node.bonus}
                        visited=visited+1
                    end
                end
            end
        end
        -- Score replies before pruning; immediate gains can hide a losing response.
        beam=next_beam
    end
    return champion,{nodes=visited,depth=0,value=best}
end
function M.choose(s,actions,config,expired)
    if config.algorithm=='uct' then
        return wesnoth.require('~add-ons/search_teacher/lua/monte_search.lua').choose(s,actions,config,expired)
    end
    if config.algorithm=='pvs' and not s.ffa then
        return wesnoth.require('~add-ons/search_teacher/lua/tree_search.lua').choose(s,actions,config,expired)
    end
    local action,stats=M.beam(s,actions,config,expired)
    stats.algorithm=config.algorithm=='pvs' and 'beam_ffa' or 'beam'
    return action,stats
end
return M
