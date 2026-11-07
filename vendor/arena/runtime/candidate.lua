-- One normal native CA, instrumented for the contest; not used by installed bots.
local judge = wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M = {}

local function state()
    local side = wesnoth.current.side
    judge.states[side] = judge.states[side] or {first=true, calls=0, disabled=false}
    return judge.states[side], side
end

local function fail(s, message)
    s.error = tostring(message)
    return 1000000
end

function M:evaluation(cfg, data)
    local s, side = state()
    s.data=data;s.cfg=cfg
    if s.disabled or judge.done() then return 0 end
    s.calls = s.calls + 1
    if s.round ~= wesnoth.current.turn then s.round=wesnoth.current.turn; s.calls=1 end
    local options = judge.options()
    s.budget = s.first and options.first_timeout or options.timeout
    s.was_first=s.first
    s.started = wesnoth.ms_since_init()
    judge.emit('CALL', {side=side, phase='evaluation', budget=s.budget, first=s.first})
    local ok, score = pcall(function()
        if s.calls > options.max_actions then error('candidate-action limit exceeded') end
        if not s.module then
            s.module = wesnoth.dofile(cfg.entry)
            assert(type(s.module)=='table' and type(s.module.evaluation)=='function' and type(s.module.execution)=='function',
                'bot.lua must return evaluation and execution functions')
        end
        local training = options.learning and options.learning[tostring(side)]
        if training then data.sampling_seed=training.sampling_seed;data.training=training end
        local score = s.module:evaluation(cfg, data)
        if training then
            if training.teacher and score==0 then
                local collector=wesnoth.require '~add-ons/arena_runtime/collector.lua'
                collector.finish(data,training)
            elseif not training.teacher and score==0 and data.learning_record then
                data.learning_record.executed=true
                judge.emit('LEARN',data.learning_record)
                data.learning_record=nil
            end
        end
        return score
    end)
    s.first = false
    if wesnoth.ms_since_init()-s.started > s.budget*1000 then return fail(s,'candidate evaluation timeout') end
    if not ok then return fail(s,score) end
    if type(score)~='number' or score~=score or score<0 or score>1000000 then return fail(s,'evaluation score must be finite and in [0,1000000]') end
    if score==0 then judge.emit('RETURN', {side=side, phase='evaluation', score=score,
        elapsed_ms=wesnoth.ms_since_init()-s.started,budget=s.budget,first=s.was_first}) end
    return score
end

function M:execution(cfg, data)
    local s, side = state()
    if not s.error then
        judge.emit('EXECUTE', {side=side})
        local originals = {}
        for _, name in ipairs {'move','move_full','attack','recruit','recall','stopunit_moves','stopunit_attacks','stopunit_all'} do
            if ai[name] then
                local original=ai[name]
                originals[name]=original
                ai[name]=function(...)
                    local result=original(...)
                    local interrupted=(name=='move' or name=='move_full') and result and result.gamestate_changed
                        and (result.status==2005 or result.status==2006)
                    if result and result.ok==false and not interrupted then error('illegal native action: '..tostring(result.result)) end
                    return result
                end
            end
        end
        local training=judge.options().learning and judge.options().learning[tostring(side)]
        local undo
        if training and training.teacher then
            undo=wesnoth.require('~add-ons/arena_runtime/collector.lua').wrap(data,training)
        end
        local ok, message = pcall(s.module.execution, s.module, cfg, data)
        if undo then undo(ok) end
        if training and not training.teacher and data.learning_record then
            data.learning_record.executed=ok
            judge.emit('LEARN',data.learning_record)
            data.learning_record=nil
        end
        for name,original in pairs(originals) do ai[name]=original end
        if not ok then s.error=tostring(message) end
        if wesnoth.ms_since_init()-s.started > s.budget*1000 then s.error='candidate-action timeout' end
    end
    judge.emit('RETURN', {side=side, phase='execution',elapsed_ms=wesnoth.ms_since_init()-s.started,
        budget=s.budget,first=s.was_first})
    if s.error then
        s.disabled=true
        judge.disqualify(side,s.error)
    else judge.check() end
end

return M
