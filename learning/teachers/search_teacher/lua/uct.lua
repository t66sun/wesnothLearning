-- Stochastic local tree search with a separate utility component per player.
local U={}
function U.solve(root,model,config,expired,rng)
    local records={};local root_actions=model.actions(root);local root_player=model.player(root)
    local baseline={};for side=1,model.players do baseline[side]=model.evaluate(root,side) end
    local stats={simulations=0,nodes=0,sampled_combats=0,algorithm='uct',root_visits={},root_values={}}
    local horizon=config.mc_depth or 8;local scale=(config.mc_scale or 50)*1000
    local function record(node,depth)
        local key=model.key(node)..':'..depth
        if not records[key] then
            local row={visits=0,arms={}}
            for _,a in ipairs(model.actions(node)) do row.arms[#row.arms+1]={action=a,visits=0,total={}} end
            records[key]=row
        end
        return records[key]
    end
    for _=1,config.mc_iterations or 96 do
        if expired() then break end
        local node=root;local path={};local complete=true
        for depth=1,horizon do
            if expired() then complete=false;break end
            if model.terminal(node) then break end
            local row=record(node,depth);local side=model.player(node)
            if expired() then complete=false;break end
            local arm,best=nil,-math.huge
            for _,a in ipairs(row.arms) do
                local score=a.visits==0 and math.huge or (a.total[side] or 0)/a.visits+
                    (config.ucb or .7)*math.sqrt(math.log(row.visits+1)/a.visits)
                if not arm or score>best then arm,best=a,score end
            end
            if not arm then break end
            path[#path+1]={row=row,arm=arm}
            node=model.apply(node,arm.action,rng);stats.nodes=stats.nodes+1
            if arm.action.kind=='combat' then stats.sampled_combats=stats.sampled_combats+1 end
        end
        if expired() then complete=false end
        if not complete then break end
        local values={}
        for side=1,model.players do
            local delta=model.evaluate(node,side)-baseline[side]
            values[side]=.5+delta/(2*(scale+math.abs(delta)))
        end
        for _,step in ipairs(path) do
            step.row.visits=step.row.visits+1;step.arm.visits=step.arm.visits+1
            for side=1,model.players do step.arm.total[side]=(step.arm.total[side] or 0)+values[side] end
        end
        stats.simulations=stats.simulations+1
    end
    local champion=root_actions[1];local best=-math.huge;local root_record=records[model.key(root)..':1']
    local covered=root_record and #root_record.arms>0 or false
    if root_record then
        for _,arm in ipairs(root_record.arms) do
            stats.root_visits[arm.action.key]=arm.visits
            if arm.visits>0 then stats.root_values[arm.action.key]=arm.total[root_player]/arm.visits end
            if arm.visits==0 then covered=false end
        end
        if covered then for _,arm in ipairs(root_record.arms) do
            local value=arm.total[root_player]/arm.visits
            if value>best then champion,best=arm.action,value end
        end end
    end
    stats.root_covered=covered;stats.utility=covered and best or nil;stats.depth=covered and horizon or 0
    return champion,stats
end
return U
