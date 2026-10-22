local O=wesnoth.require '~add-ons/@ADDON@/lua/observation.lua'
local C=wesnoth.require '~add-ons/@ADDON@/lua/candidates.lua'
local N=wesnoth.require '~add-ons/@ADDON@/lua/network.lua'
local R=wesnoth.require '~add-ons/@ADDON@/lua/routing.lua'
local config=wesnoth.require '~add-ons/@ADDON@/lua/config.lua'
local schema=wesnoth.require '~add-ons/@ADDON@/lua/features.lua'
local M={}
local T=wesnoth.require '~add-ons/@ADDON@/lua/teacher.lua'
local S=wesnoth.require '~add-ons/@ADDON@/lua/spatial.lua'
local W=wesnoth.require '~add-ons/@ADDON@/lua/rewards.lua'
function M:evaluation(cfg,data)
    data.memory=data.memory or {}
    local fmt=R.select(data.memory)
    if not data.weights then data.weights=wesnoth.require('~add-ons/@ADDON@/lua/weights_'..fmt..'.lua') end
    local started=wesnoth.ms_since_init()
    local obs=O.capture(data.memory)
    local raw=W.capture(obs,data.memory,data.training~=nil)
    local candidates,timing=C.generate(obs,config.candidate_budget_ms)
    if data.training and data.training.dagger_entry then T.observe(data,obs) end
    data.neural_memory=data.neural_memory or {}
    local scores,value,pending=N.forward(data.weights,obs.global,obs.opponents,candidates,obs.spatial,data.neural_memory,wesnoth.current.turn)
    data.pending_memory=pending
    if config.mode=='rule' then for i,a in ipairs(candidates) do scores[i]=a.rule end end
    local function random()
        data.sampling_rng=((data.sampling_rng or data.sampling_seed or (wesnoth.current.side*999983+1))*16807)%2147483647
        if data.sampling_rng==0 then data.sampling_rng=1 end
        return data.sampling_rng/2147483647
    end
    local choice,logp=N.choose(scores,config.mode=='sample',random)
    data.plan=candidates[choice]
    data.learning_record={schema=schema.version,global=obs.global,opponents=obs.opponents,spatial=obs.spatial,candidates=candidates,
        choice=choice-1,log_probability=logp,value=value,version=config.version,
        side=wesnoth.current.side,turn=wesnoth.current.turn,timing=timing,teacher=false,source='policy',format=fmt,
        diagnostics=C.diagnostics(obs,data.plan)}
    data.learning_record.potential=obs.potential
    data.learning_record.reward_raw=raw
    data.learning_record.committed=false
    data.plan_obs=obs
    data.learning_record.timing.inference_ms=wesnoth.ms_since_init()-started-timing.ms
    local actual={}
    for _,key in ipairs {'kind','x','y','tx','ty','ex','ey','type','weapon','full'} do actual[key]=data.plan[key] end
    data.learning_record.actual=actual
    data.learning_record.dagger=T.query(data,obs,candidates,scores,data.training)
    if data.plan.kind=='end_turn' then
        if data.end_turn_committed~=wesnoth.current.turn then
            data.learning_record.memory_write=S.memory_observation(obs)
            N.commit(data.neural_memory,pending);C.remember(obs,data.plan);data.end_turn_committed=wesnoth.current.turn
            data.learning_record.committed=true;data.learning_record.reward_after=raw
        end
        return 0
    end
    return 100000
end
function M:execution(cfg,data)
    local outcome=C.execute(data.plan)
    data.learning_record.outcome=outcome
    if not outcome.changed then data.learning_record.committed=false;return end
    C.remember(data.plan_obs,data.plan)
    local post=O.capture(data.memory)
    if data.neural_memory.turn~=wesnoth.current.turn then
        data.learning_record.memory_write=S.memory_observation(post)
        local _,_,pending=N.forward(data.weights,post.global,post.opponents,{},post.spatial,data.neural_memory,wesnoth.current.turn)
        N.commit(data.neural_memory,pending)
    end
    data.learning_record.committed=true
    data.learning_record.reward_after=W.capture(post,data.memory,data.training~=nil)
    C.outcome(data.plan,data.learning_record and data.learning_record.diagnostics)
end
function M:bootstrap(cfg,data,side)
    local function copy(v) if type(v)~='table' then return v end;local out={};for k,x in pairs(v) do out[k]=copy(x) end;return out end
    local obs=O.capture(copy(data.memory),side)
    S.actions(obs,{})
    local _,value=N.forward(data.weights,obs.global,obs.opponents,{},obs.spatial,copy(data.neural_memory or {}),wesnoth.current.turn)
    return {side=side,value=value,potential=obs.potential,reward_raw=W.capture(obs,copy(data.memory),{judge=data.training~=nil,preview=true}),turn=wesnoth.current.turn}
end
return M
