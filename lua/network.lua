-- Row-major float32 weights, accumulated with native Lua numbers.
local M = {}
local relational=wesnoth.require '~add-ons/@ADDON@/lua/relational.lua'
M.commit=relational.commit
local function sparse(x)
    local indices,values={},{}
    for j=1,#x do if x[j]~=0 then indices[#indices+1]=j;values[#values+1]=x[j] end end
    return indices,values
end
local function linear(x, layer, relu)
    local y = {}
    local indices,values=sparse(x)
    for i=1,#layer.weight do
        local row=layer.weight[i]
        local v = layer.bias[i]
        for j=1,#indices do v=v+row[indices[j]]*values[j] end
        y[i] = relu and math.max(0, v) or v
    end
    return y
end
local function append(to, from)
    for _, v in ipairs(from) do to[#to+1] = v end
end
function M.forward(weights, global, opponents, candidates, spatial, memory, turn)
    if weights.architecture_id=='relational_v5' then return relational.forward(weights,global,opponents,candidates,spatial,memory or {},turn or 0) end
    local mean, maximum = {}, {}
    for i=1,16 do mean[i]=0; maximum[i]=0 end
    for _, opponent in ipairs(opponents) do
        local e = linear(opponent, weights.opponent[1], true)
        for i=1,16 do
            mean[i] = mean[i] + e[i] / #opponents
            maximum[i] = math.max(maximum[i], e[i])
        end
    end
    local context = {}
    append(context, global); append(context, mean); append(context, maximum)
    local values = context
    for i, layer in ipairs(weights.value) do values=linear(values,layer,i<#weights.value) end
    local scores = {}
    -- The context is identical for all 128 actions; multiply it once.
    local first=weights.scorer[1]
    local base={}
    local context_indices,context_values=sparse(context)
    for i=1,#first.weight do
        local row=first.weight[i]
        local v=first.bias[i]
        for j=1,#context_indices do v=v+row[context_indices[j]]*context_values[j] end
        base[i]=v
    end
    -- Several legal destinations can have exactly the same model input. Reuse
    -- their score within this observation; binary keys preserve every bit.
    local memo={}
    for _, candidate in ipairs(candidates) do
        local parts={}
        for i,v in ipairs(candidate.features) do parts[i]=string.pack('d',v) end
        local key=table.concat(parts)
        if memo[key]~=nil then
            scores[#scores+1]=memo[key]
        else
        local features={}
        for i=1,#candidate.features-1 do features[i]=candidate.features[i] end
        append(features,assert(weights.unit_embedding[candidate.features[#candidate.features]+1],'invalid unit identity'))
        local indices,values=sparse(features)
        local x={}
        for i=1,#first.weight do
            local row=first.weight[i]
            local v=base[i]
            for j=1,#indices do v=v+row[#context+indices[j]]*values[j] end
            x[i]=math.max(0,v)
        end
        for i=2,#weights.scorer do x=linear(x,weights.scorer[i],i<#weights.scorer) end
        memo[key]=x[1]
        scores[#scores+1] = x[1]
        end
    end
    return scores, values[1]
end
function M.choose(scores, stochastic, random)
    local best=1
    for i=2,#scores do if scores[i]>scores[best] then best=i end end
    local probabilities, sum = {}, 0
    for i,s in ipairs(scores) do probabilities[i]=math.exp(s-scores[best]);sum=sum+probabilities[i] end
    for i,p in ipairs(probabilities) do probabilities[i]=p/sum end
    local chosen=best
    if stochastic then
        local roll=(random or math.random)()
        chosen=#scores
        for i,p in ipairs(probabilities) do
            roll=roll-p
            if roll<=0 then chosen=i;break end
        end
    end
    return chosen, math.log(math.max(probabilities[chosen],1e-300))
end
return M
