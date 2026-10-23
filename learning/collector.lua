-- Training-only Astra instrumentation. One label per completed native macro action.
-- Astra walks a planned path one hex at a time; those implementation steps are
-- collected as one move intent. Candidate generation never sees the teacher plan.
local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
local C=wesnoth.require '~add-ons/LearningSupport/lua/candidates.lua'
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local schema=wesnoth.require '~add-ons/LearningSupport/lua/features.lua'
local config=wesnoth.require '~add-ons/LearningSupport/lua/config.lua'
local R=wesnoth.require '~add-ons/LearningSupport/lua/routing.lua'
local M={}
local W=wesnoth.require '~add-ons/LearningSupport/lua/rewards.lua'
local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
local function record(data,training)
    data.collector_memory=data.collector_memory or {}
    local obs=O.capture(data.collector_memory)
    local candidates,timing=C.generate(obs,config.candidate_budget_ms)
    -- Post-action diagnostics need pre-action moves and identity, not native
    -- handles that combat can invalidate when a unit dies or advances.
    local own,occupied={},{}
    for i,u in ipairs(obs.own) do own[i]={moves=u.moves,x=u.x,y=u.y,canrecruit=u.canrecruit} end
    for key,u in pairs(obs.occupied) do occupied[key]={id=u.id} end
    obs.own=own;obs.occupied=occupied
    return {schema=schema.version,global=obs.global,opponents=obs.opponents,spatial=obs.spatial,candidates=candidates,
        choice=-1,log_probability=0,value=0,version=training.version,
        side=wesnoth.current.side,turn=wesnoth.current.turn,timing=timing,teacher=training.teacher,
        source='astra',format=R.select(data.collector_memory),reward_raw=W.capture(obs,data.collector_memory,true)},obs
end
local function loc(v) return v.x or v[1],v.y or v[2] end
local function match(r,a)
    r.actual=a
    r.representable=a.kind=='end_turn' or a.kind=='recruit' or a.kind=='move'
        or (a.kind=='attack' or a.kind=='move_attack') and a.weapon~=nil and a.weapon>0
    local fields={end_turn={},recruit={'type','x','y'},move={'x','y','tx','ty','full'},
        attack={'x','y','tx','ty','weapon'},move_attack={'x','y','tx','ty','ex','ey','weapon'}}
    for i,c in ipairs(r.candidates) do
        local same=c.kind==a.kind
        for _,key in ipairs(fields[a.kind] or {}) do if c[key]~=a[key] then same=false end end
        if same then r.choice=i-1;break end
    end
end
function M.finish(data,training)
    local r,obs=record(data,training)
    match(r,{kind='end_turn'})
    r.diagnostics=C.diagnostics(obs,r.candidates[1],r.candidates);C.remember(obs,r.candidates[1])
    r.committed=true;r.memory_write=S.memory_observation(obs);r.reward_after=r.reward_raw
    judge.emit('LEARN',r)
end
function M.wrap(data,training)
    local originals={};local r,obs=record(data,training)
    local moving_id,from_x,from_y,full,changed,actual
    local microsteps,noops=0,0
    for _,name in ipairs {'move','move_full','attack','recruit','stopunit_moves','stopunit_attacks','stopunit_all','recall'} do
        local original=ai[name]
        if original then
            originals[name]=original
            ai[name]=function(...)
                local args={...};local candidate
                if name=='move' or name=='move_full' then
                    local x,y=loc(args[1])
                    if not moving_id then
                        local u=wesnoth.units.get(x,y)
                        if u then moving_id=u.id;from_x=x;from_y=y end
                    end
                elseif name=='recruit' then
                    local x,y=loc(args[2]);candidate={kind='recruit',type=args[1],x=x,y=y}
                elseif name=='attack' then
                    local x,y=loc(args[1]);local ex,ey=loc(args[2])
                    if moving_id and (x~=from_x or y~=from_y) then
                        candidate={kind='move_attack',x=from_x,y=from_y,tx=x,ty=y,ex=ex,ey=ey,weapon=args[3]}
                    else candidate={kind='attack',x=x,y=y,tx=ex,ty=ey,weapon=args[3]} end
                else candidate={kind=name} end
                local result=original(...)
                local succeeded=result and result.ok
                if succeeded and result.gamestate_changed~=false then
                    changed=true
                    if name=='move' or name=='move_full' then full=name=='move_full';microsteps=microsteps+1
                    else actual=candidate end
                elseif name=='move' or name=='move_full' then noops=noops+1 end
                return result
            end
        end
    end
    return function(executed)
        for name,original in pairs(originals) do ai[name]=original end
        if executed==false or not changed then return end
        local moving
        if moving_id then
            for _,u in ipairs(wesnoth.units.find_on_map {side=obs.side}) do
                if u.id==moving_id then moving=u;break end
            end
        end
        if not actual and moving and (moving.x~=from_x or moving.y~=from_y) then
            actual={kind='move',x=from_x,y=from_y,tx=moving.x,ty=moving.y,full=full or false}
        end
        if not actual then return end
        -- Label the teacher's selected intent, with partial execution recorded
        -- separately. Deployment also stops paths on newly visible enemies.
        if moving_id then
            r.outcome={alive=moving~=nil,attacked=actual.kind=='move_attack' or actual.kind=='attack'}
            if moving then r.outcome.x=moving.x;r.outcome.y=moving.y;r.outcome.moves=moving.moves end
            local plan=data.plan
            if plan and plan.kind=='move' then
                actual={kind='move',x=from_x,y=from_y,tx=plan.tx,ty=plan.ty,full=true}
            elseif plan and plan.kind=='combat' then
                actual={kind=from_x==plan.tx and from_y==plan.ty and 'attack' or 'move_attack',
                    x=from_x,y=from_y,tx=plan.tx,ty=plan.ty,weapon=plan.weapon}
                if actual.kind=='attack' then actual.tx=plan.ex;actual.ty=plan.ey
                else actual.ex=plan.ex;actual.ey=plan.ey end
            end
        end
        match(r,actual)
        r.intent=actual
        r.microsteps=microsteps;r.noop_calls=noops
        local post=O.capture(data.collector_memory)
        r.committed=true;r.memory_write=S.memory_observation(post);r.reward_after=W.capture(post,data.collector_memory,true)
        if r.choice>=0 then
            local action=r.candidates[r.choice+1]
            r.diagnostics=C.diagnostics(obs,action,r.candidates);C.remember(obs,action);C.outcome(action,r.diagnostics)
        end
        judge.emit('LEARN',r)
    end
end
return M
