-- Native replay observer, training only. Original commands execute in 1.18.8.
local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
local C=wesnoth.require '~add-ons/LearningSupport/lua/candidates.lua'
local schema=wesnoth.require '~add-ons/LearningSupport/lua/features.lua'
local config=wesnoth.require '~add-ons/LearningSupport/lua/config.lua'
local M={}
local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
local function json(v)
    if v==nil then return 'null' end
    if type(v)=='number' or type(v)=='boolean' then return tostring(v) end
    if type(v)=='string' then return '"'..v:gsub('[%z\1-\31\\"]',function(c) return string.format('\\u%04x',string.byte(c)) end)..'"' end
    local out={}
    if #v>0 then for _,x in ipairs(v) do out[#out+1]=json(x) end;return '['..table.concat(out,',')..']' end
    for k,x in pairs(v) do out[#out+1]=json(tostring(k))..':'..json(x) end
    return '{'..table.concat(out,',')..'}'
end
local function emit(e) std_print('LEARNING_HUMAN '..json(e)) end
function M.setup(options)
    local memories={};local pending;local observed=0;local completed=false
    local function flush()
        if pending then
            pending.result_observed=true
            local post=O.capture(memories[pending.side],pending.side)
            pending.memory_write=S.memory_observation(post);pending.memory_write.turn=pending.turn
            pending.committed=true
            emit {event='sample',record=pending};pending=nil
        end
    end
    wesnoth.custom_synced_commands.learning_result=flush
    wesnoth.custom_synced_commands.learning_observe=function(cfg)
        flush()
        local index=tonumber(cfg.index);local actual=assert(options.actions[index+1])
        assert(index==observed,'native command sequence mismatch');observed=observed+1
        local side=wesnoth.current.side
        assert(side==actual.side,'native side/action alignment mismatch')
        assert(wesnoth.sides[side].controller=='human','AI takeover: refusing human label')
        memories[side]=memories[side] or {}
        -- The game kernel has no global 'ai': debug_ai returns the AI state whose 'ai' field holds the functions table.
        local previous_ai=rawget(_G,'ai')
        ai=assert(wesnoth.sides.debug_ai(side).ai,'debug AI query context unavailable')
        local obs=O.capture(memories[side]);local candidates,timing=C.generate(obs,config.candidate_budget_ms)
        ai=previous_ai
        local choice=-1
        for i,c in ipairs(candidates) do
            local same=true
            for _,key in ipairs {'kind','x','y','tx','ty','weapon','type','full'} do if c[key]~=actual[key] then same=false end end
            if same then choice=i-1;C.remember(obs,c);break end
        end
        pending={schema=schema.version,format=options.format,source='human',human_control=true,
            global=obs.global,opponents=obs.opponents,spatial=obs.spatial,candidates=candidates,choice=choice,
            actual=actual,action_index=index,side=side,turn=wesnoth.current.turn,timing=timing,
            log_probability=0,value=0,version=options.observer_version}
    end
    local function complete()
        if completed then return end
        assert(observed==options.expected_actions,'replay ended before all human intents were observed')
        completed=true
        flush()
        emit {event='complete',source_sha256=options.source_sha256,observer_version=options.observer_version,expected_actions=options.expected_actions}
    end
    wesnoth.custom_synced_commands.learning_complete=function()
        complete()
        wesnoth.wml_actions.endlevel {result='victory',linger_mode=false,carryover_report=false,carryover_percentage=0,replay_save=false}
    end
    -- A winning native action can end a replay before the appended marker.
    wesnoth.game_events.add {name='victory,defeat',first_time_only=false,action=complete}
end
return M
