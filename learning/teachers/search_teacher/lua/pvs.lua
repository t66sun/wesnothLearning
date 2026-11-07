-- Integer-valued principal variation search; the caller owns the local model.
local P={}
function P.solve(root,model,depth,expired,cache,preferred)
    cache=cache or {};preferred=preferred or {}
    local stats={nodes=0,cutoffs=0,researches=0,cache_hits=0}
    local function visit(node,left,alpha,beta)
        if expired() then return nil end
        stats.nodes=stats.nodes+1
        if left==0 or model.terminal(node) then return model.evaluate(node) end
        local identity=model.key(node);local key=identity..':'..left
        local entry=cache[key]
        if entry and (entry.bound=='exact' or entry.bound=='lower' and entry.value>=beta or
                      entry.bound=='upper' and entry.value<=alpha) then
            stats.cache_hits=stats.cache_hits+1;return entry.value,entry.action
        end
        local alpha0,beta0=alpha,beta;local maximize=model.maximizing(node)
        local choices=model.actions(node);if expired() then return nil end
        if #choices==0 then return model.evaluate(node) end
        local ordered={};local first=preferred[identity]
        for _,a in ipairs(choices) do if a.key==first then ordered[#ordered+1]=a end end
        for _,a in ipairs(choices) do if a.key~=first then ordered[#ordered+1]=a end end
        local best=maximize and -math.huge or math.huge;local action
        for i,a in ipairs(ordered) do
            if expired() then return nil end
            local child=model.apply(node,a);local value
            if i==1 then value=visit(child,left-1,alpha,beta)
            elseif maximize then
                value=visit(child,left-1,alpha,alpha+1)
                if value and value>alpha and value<beta then
                    stats.researches=stats.researches+1;value=visit(child,left-1,alpha,beta)
                end
            else
                value=visit(child,left-1,beta-1,beta)
                if value and value<beta and value>alpha then
                    stats.researches=stats.researches+1;value=visit(child,left-1,alpha,beta)
                end
            end
            if value==nil then return nil end
            if not action or maximize and value>best or not maximize and value<best then best,action=value,a end
            if maximize then alpha=math.max(alpha,best) else beta=math.min(beta,best) end
            if alpha>=beta then stats.cutoffs=stats.cutoffs+1;break end
        end
        preferred[identity]=action.key
        if (cache.count or 0)<4096 then
            if not cache[key] then cache.count=(cache.count or 0)+1 end
            cache[key]={value=best,action=action,bound=best<=alpha0 and 'upper' or best>=beta0 and 'lower' or 'exact'}
        end
        return best,action
    end
    local value,action=visit(root,depth,-math.huge,math.huge)
    return action,value,stats
end
return P
