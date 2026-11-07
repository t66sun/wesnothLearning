-- Training-only planning. Frozen teachers receive a disposable public ledger.
local Memory=wesnoth.require '~add-ons/@ADDON@/lua/teacher_memory.lua'
local M={}
local function copy(v) if type(v)~='table' then return v end;local t={};for k,x in pairs(v) do t[k]=copy(x) end;return t end
local function intent(plan)
    if not plan then return {kind='end_turn'} end
    if plan.kind=='combat' then
        if plan.x==plan.tx and plan.y==plan.ty then return {kind='attack',x=plan.x,y=plan.y,tx=plan.ex,ty=plan.ey,weapon=plan.weapon} end
        return {kind='move_attack',x=plan.x,y=plan.y,tx=plan.tx,ty=plan.ty,ex=plan.ex,ey=plan.ey,weapon=plan.weapon}
    end
    if plan.kind=='move' then return {kind='move',x=plan.x,y=plan.y,tx=plan.tx,ty=plan.ty,full=true} end
    return {kind='recruit',type=plan.type,x=plan.x,y=plan.y}
end
function M.observe(data,obs)
    data.teacher_ledger=data.teacher_ledger or {}
    Memory.observe(data.teacher_ledger,obs)
end
function M.plan(data,training)
    local first=not data.teacher_queried
    data.teacher_queried=true
    local budget=first and (training.dagger_first_timeout or 10) or (training.dagger_timeout or 1)
    local started=wesnoth.ms_since_init()
    if data.teacher_query_begin then data.teacher_query_begin(budget,first) end
    local ledger=copy(data.teacher_ledger or {})
    local originals={};local function forbidden() error('teacher query cannot execute or consume random streams') end
    for _,name in ipairs {'move','move_full','attack','recruit','recall','stopunit_moves','stopunit_attacks','stopunit_all'} do
        if ai[name] then originals[name]=ai[name];ai[name]=forbidden end
    end
    local random=math.random;math.random=forbidden
    local game_random=mathx and mathx.random
    if game_random then mathx.random=forbidden end
    local ok,message=pcall(function()
        data.teacher_module=data.teacher_module or wesnoth.dofile(training.dagger_entry)
        data.teacher_module:evaluation({},ledger)
    end)
    math.random=random;for name,f in pairs(originals) do ai[name]=f end
    if game_random then mathx.random=game_random end
    local elapsed=wesnoth.ms_since_init()-started
    data.teacher_query_ms=(data.teacher_query_ms or 0)+elapsed
    if data.teacher_query_end then data.teacher_query_end(elapsed) end
    if elapsed>budget*1000 then ok=false;message='teacher query timeout' end
    local result={query_ms=elapsed,query_budget=budget,first_query=first,query_only=true}
    if not ok then result.error=tostring(message);result.choice=-1;return nil,result end
    return copy(ledger.plan or {kind='end_turn'}),result
end
function M.query(data,obs,candidates,scores,training)
    if not training or not training.dagger_entry then return nil end
    M.observe(data,obs)
    data.dagger_decisions=(data.dagger_decisions or 0)+1;data.dagger_queries=data.dagger_queries or 0
    if data.dagger_queries>=32 or data.dagger_queries>=math.floor(data.dagger_decisions*.25) then return nil end
    local maximum=-math.huge;for _,v in ipairs(scores) do maximum=math.max(maximum,v) end
    local total=0;local entropy=0
    for _,v in ipairs(scores) do total=total+math.exp(v-maximum) end
    for _,v in ipairs(scores) do local p=math.exp(v-maximum)/total;entropy=entropy-p*math.log(math.max(p,1e-300)) end
    local urgent=entropy>.6*math.log(math.max(2,#scores))
    for _,a in ipairs(candidates) do if a.kind=='attack' or a.kind=='move_attack' or a.category=='explore' then urgent=true end end
    if not urgent and data.dagger_decisions%8~=0 then return nil end
    data.dagger_queries=data.dagger_queries+1
    local plan,result=M.plan(data,training)
    if result.error then return result end
    local actual=plan.kind=='end_turn' and plan or intent(plan);local choice=-1
    local fields={end_turn={},recruit={'type','x','y'},move={'x','y','tx','ty','full'},attack={'x','y','tx','ty','weapon'},move_attack={'x','y','tx','ty','ex','ey','weapon'}}
    for i,c in ipairs(candidates) do
        local same=c.kind==actual.kind;for _,key in ipairs(fields[actual.kind]) do if c[key]~=actual[key] then same=false end end
        if same then choice=i-1;break end
    end
    for key,value in pairs(training.dagger_identity or {teacher='gpt6astra',teacher_impl='astra_native'}) do result[key]=value end
    result.actual=actual;result.intent=actual;result.choice=choice
    result.source=result.teacher_contract and 'teacher' or 'astra'
    if result.teacher_contract then result.teacher_impl=result.teacher end
    result.data_role='dagger';result.entropy=entropy;result.representable=true
    return result
end
return M
