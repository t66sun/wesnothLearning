-- Training-only planning. The frozen Astra source receives a separate legal ledger.
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
    data.teacher_ledger=data.teacher_ledger or {owners={},home={}}
    local ledger=data.teacher_ledger
    for _,u in ipairs(obs.own) do if not ledger.home[u.id] then ledger.home[u.id]={u.x,u.y} end end
    for key,owner in pairs(obs.memory.villages or {}) do ledger.owners[key]=owner end
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
    data.teacher_module=data.teacher_module or wesnoth.dofile(training.dagger_entry)
    local ledger=copy(data.teacher_ledger)
    local originals={};local function forbidden() error('teacher query cannot execute or consume random streams') end
    for _,name in ipairs {'move','move_full','attack','recruit','recall','stopunit_moves','stopunit_attacks','stopunit_all'} do
        if ai[name] then originals[name]=ai[name];ai[name]=forbidden end
    end
    local random=math.random;math.random=forbidden
    local ok,message=pcall(data.teacher_module.evaluation,data.teacher_module,{},ledger)
    math.random=random;for name,f in pairs(originals) do ai[name]=f end
    if not ok then return {error=tostring(message),choice=-1,query_only=true} end
    local actual=intent(ledger.plan);local choice=-1
    local fields={end_turn={},recruit={'type','x','y'},move={'x','y','tx','ty','full'},attack={'x','y','tx','ty','weapon'},move_attack={'x','y','tx','ty','ex','ey','weapon'}}
    for i,c in ipairs(candidates) do
        local same=c.kind==actual.kind;for _,key in ipairs(fields[actual.kind]) do if c[key]~=actual[key] then same=false end end
        if same then choice=i-1;break end
    end
    return {actual=actual,intent=actual,choice=choice,source='astra',teacher='gpt6astra',teacher_impl='astra_native',
        query_only=true,data_role='dagger',entropy=entropy,representable=true}
end
return M
