-- Judge-only instrumentation. All game rules and action execution remain native.
local M = { states = {} }
local configured = false
local config, finished
local eliminated, faults = {}, {}

local function json(value)
    if value == nil then return 'null' end
    if type(value) == 'boolean' or type(value) == 'number' then return tostring(value) end
    if type(value) == 'string' then
        return '"' .. value:gsub('[%z\1-\31\\"]', function(c)
            if c == '\\' then return '\\\\' end
            if c == '"' then return '\\"' end
            return string.format('\\u%04x', string.byte(c))
        end) .. '"'
    end
    local result = {}
    if #value > 0 then
        for _, v in ipairs(value) do result[#result+1] = json(v) end
        return '[' .. table.concat(result, ',') .. ']'
    end
    for k, v in pairs(value) do result[#result+1] = json(tostring(k)) .. ':' .. json(v) end
    table.sort(result)
    return '{' .. table.concat(result, ',') .. '}'
end

function M.emit(kind, payload)
    if config then std_print('ARENA2 ' .. config.token .. ' ' .. kind .. ' ' .. json(payload)) end
end

function M.snapshot()
    local units, gold, villages = {}, {}, {}
    for _, u in ipairs(wesnoth.units.find_on_map {}) do
        units[#units+1] = {id=u.id, side=u.side, type=u.type, x=u.x, y=u.y,
            hp=u.hitpoints, max_hp=u.max_hitpoints, moves=u.moves, xp=u.experience}
    end
    table.sort(units, function(a,b) return a.id < b.id end)
    for i, s in ipairs(wesnoth.sides) do gold[i] = s.gold end
    for _, p in ipairs(wesnoth.map.find {gives_income=true}) do
        villages[#villages+1] = {p[1], p[2], wesnoth.map.get_owner(p) or 0}
    end
    return {turn=wesnoth.current.turn, side=wesnoth.current.side, units=units, gold=gold, villages=villages}
end

local function metric_snapshot(side, event)
    local training=config.learning and config.learning[tostring(side)]
    if not training then return end
    local ok,row=pcall(function()
        local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
        local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
        local W=wesnoth.require '~add-ons/LearningSupport/lua/rewards.lua'
        local schema=wesnoth.require '~add-ons/LearningSupport/lua/features.lua'
        local state=M.states[side];local data=state and state.data or {}
        local memory=data.collector_memory or data.memory or {}
        local obs=O.capture(memory,side)
        local snapshot=S.memory_observation(obs)
        snapshot.side=side;snapshot.metric_event=event
        snapshot.reward_raw=W.capture(obs,memory,true)
        snapshot.source=training.teacher and 'astra' or 'policy';snapshot.teacher=training.teacher or false
        snapshot.rules_version=schema.rules_sha256
        return snapshot
    end)
    if ok then M.emit('METRIC',row) else M.emit('METRIC_ERROR',{side=side,error=tostring(row)}) end
end

local function living()
    local sides = {}
    for side=1,#wesnoth.sides do
        if not eliminated[side] then
            local leaders = wesnoth.units.find_on_map {side=side, canrecruit=true}
            local alive = false
            for _, u in ipairs(leaders) do if u.hitpoints > 0 then alive=true end end
            if alive then sides[#sides+1] = side else
                eliminated[side] = wesnoth.current.turn
                -- Defeated leaders eliminate their faction in the FFA profile.
                wesnoth.wml_actions.kill {side=side, hitpoints='1-99999', fire_event=false, animate=false}
                metric_snapshot(side,'eliminated')
                M.emit('ELIMINATED', {side=side, turn=wesnoth.current.turn})
            end
        end
    end
    return sides
end

function M.finish(reason)
    if finished then return end
    local survivors = living()
    if reason~='turn_limit' then
        for _,side in ipairs(survivors) do metric_snapshot(side,'terminal') end
    end
    if reason=='turn_limit' and config.learning then
        for key,training in pairs(config.learning) do
            local side=tonumber(key);local s=M.states[side]
            if not training.teacher and s and s.module and s.module.bootstrap and s.data then
                local ok,observation=pcall(s.module.bootstrap,s.module,s.cfg,s.data,side)
                if ok then M.emit('BOOTSTRAP',observation)
                else M.emit('BOOTSTRAP_ERROR',{side=side,error=tostring(observation)}) end
            end
        end
    end
    finished = true
    M.emit('SNAPSHOT', M.snapshot())
    local elimination_map, fault_map = {}, {}
    for k,v in pairs(eliminated) do elimination_map[tostring(k)]=v end
    for k,v in pairs(faults) do fault_map[tostring(k)]=v end
    M.emit('RESULT', {reason=reason, survivors=survivors, eliminated=elimination_map,
        faults=fault_map, turns=math.min(wesnoth.current.turn, config.max_turns)})
    wml.variables.arena_finished = true
    wesnoth.wml_actions.endlevel {result='victory', linger_mode=false,
        carryover_report=false, carryover_percentage=0, replay_save=true}
end

function M.check()
    if finished then return end
    local survivors=living()
    if config.teams then
        local alive,count={},0
        for _,side in ipairs(survivors) do
            local team=config.teams[side]
            if not alive[team] then alive[team]=true;count=count+1 end
        end
        if count<=1 then M.finish('last_team') end
    elseif #survivors<=1 then M.finish('last_leader') end
end

function M.disqualify(side, reason)
    if faults[side] then return end
    faults[side] = tostring(reason):sub(1,1500)
    M.emit('FAULT', {side=side, reason=faults[side], turn=wesnoth.current.turn})
    if config.lenient then return end
    if config.teams then
        for other,team in ipairs(config.teams) do
            if team==config.teams[side] then
                eliminated[other]=wesnoth.current.turn
                wesnoth.wml_actions.kill {side=other,fire_event=false,animate=false}
                M.emit('ELIMINATED',{side=other,turn=wesnoth.current.turn})
            end
        end
        M.check()
        return
    end
    eliminated[side] = wesnoth.current.turn
    wesnoth.wml_actions.kill {side=side, fire_event=false, animate=false}
    M.check()
end

function M.options() return config end
function M.done() return finished end

function M.setup(options)
    if configured then return end
    configured, config = true, options
    if config.seed then math.randomseed(config.seed) end
    wesnoth.game_events.add {name='start', first_time_only=false, action=function()
        M.emit('START', {players=#wesnoth.sides, version=wesnoth.game_config.version})
        M.emit('SNAPSHOT', M.snapshot())
    end}
    wesnoth.game_events.add {name='side turn', first_time_only=false, action=function()
        if config.learning and not M.reward_initialized then
            wesnoth.require('~add-ons/LearningSupport/lua/rewards.lua').initialize_all()
            M.reward_initialized=true
            for key in pairs(config.learning) do metric_snapshot(tonumber(key),'initial') end
        end
        M.check()
        if not finished then M.emit('TURN', {side=wesnoth.current.side, turn=wesnoth.current.turn}) end
    end}
    wesnoth.game_events.add {name='side turn end', first_time_only=false, action=function()
        M.emit('SNAPSHOT', M.snapshot())
        M.emit('TURN_END', {side=wesnoth.current.side, turn=wesnoth.current.turn})
        M.check()
    end}
    wesnoth.game_events.add {name='time over', first_time_only=false, action=function() M.finish('turn_limit') end}
    wesnoth.game_events.add {name='die', first_time_only=false, action=function() M.check() end}
end

return M
