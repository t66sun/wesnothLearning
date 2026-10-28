-- Engine events are audit facts; only observer DTOs become policy inputs.
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M={}
local serial=0
local actions=0
local state={}
local function emit(frame) judge.emit('STOCK',frame) end
local function slot(side)
    local value=state[side]
    if not value then value={};state[side]=value end
    return value
end
function M.capabilities(functions,turn_query)
    emit {type='CAPABILITIES',side=wesnoth.current.side,functions=functions,
        teacher_turn=turn_query,reason='runtime Lua AI surface only; no takeover performed'}
end
function M.hook(name,callable,detail)
    emit {type='HOOK',side=wesnoth.current.side,name=name,callable=callable,detail=detail or ''}
end
-- The public DTO is built in one place so observer and engine evidence cannot drift.
function M.row(memory,viewing_side)
    local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
    local C=wesnoth.require '~add-ons/LearningSupport/lua/candidates.lua'
    local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
    local schema=wesnoth.require '~add-ons/LearningSupport/lua/features.lua'
    local routing=wesnoth.require '~add-ons/LearningSupport/lua/routing.lua'
    local obs=O.capture(memory,viewing_side)
    local candidates,timing=C.generate(obs,200)
    return {schema=schema.version,global=obs.global,opponents=obs.opponents,
        spatial=obs.spatial,candidates=candidates,timing=timing,side=obs.side,
        turn=wesnoth.current.turn,format=routing.select(memory),version='stock-events-v1',
        memory_write=S.memory_observation(obs)}
end
-- A context is the public state the observer sees immediately before the AI
-- picks its next action; the candidate loop evaluates the observer every cycle.
function M.context(row,memory)
    serial=serial+1
    local value=slot(row.side)
    value.memory=memory
    value.context={id=serial,used=false}
    emit {type='CONTEXT',id=serial,side=row.side,turn=row.turn,row=row}
end
local function after(side)
    local value=slot(side)
    local context=value.context
    if not context or not value.memory then return end
    local ok,obs=pcall(function()
        return wesnoth.require('~add-ons/LearningSupport/lua/observation.lua').capture(value.memory,side)
    end)
    if not ok then
        emit {type='AFTER_ERROR',side=side,context=context.id,error=tostring(obs)}
        return
    end
    local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
    emit {type='AFTER',side=side,context=context.id,memory_write=S.memory_observation(obs)}
end
function M.setup(sides)
    local watched={}
    for _,side in ipairs(sides) do watched[side]=true end
    wesnoth.game_events.add {name='start',first_time_only=true,action=function()
        for _,side in ipairs(sides) do
            assert(wesnoth.sides[side].controller=='ai','stock capture needs an AI side')
            wesnoth.wml_actions.modify_ai {side=side,action='add',path='stage[main_loop].candidate_action',
                {'candidate_action',{engine='lua',id='learning_stock_observer',name='learning_stock_observer',
                    max_score=1000001,location='~add-ons/LearningSupport/lua/stock_rca_capture/observer.lua'}}}
        end
    end}
    for _,kind in ipairs {'recruit','recall','moveto','attack','post advance'} do
        wesnoth.game_events.add {name=kind,first_time_only=false,action=function()
            local side=wesnoth.current.side
            if not watched[side] then return end
            local value=slot(side)
            local ec=wesnoth.current.event_context
            local x,y=ec.x1,ec.y1
            local visible=wesnoth.units.find_on_map {x=x,y=y,side=side,
                {'filter_vision',{side=side,visible='yes'}}}
            local u=visible[1]
            actions=actions+1
            local frame={type='ACTION',seq=actions,side=side,turn=wesnoth.current.turn,
                kind=kind=='post advance' and 'advance' or kind,visible=u~=nil,
                context=value.context and value.context.id}
            if u then
                frame.unit={x=x,y=y};frame.type_id=u.type
                if kind=='moveto' then
                    frame.unit={x=ec.x2,y=ec.y2};frame.to={x=x,y=y}
                elseif kind=='recruit' or kind=='recall' then frame.to={x=x,y=y}
                elseif kind=='attack' then
                    local target=wesnoth.units.find_on_map {x=ec.x2,y=ec.y2,
                        {'filter_vision',{side=side,visible='yes'}}}
                    frame.visible=target[1]~=nil
                    if frame.visible then
                        frame.target={x=ec.x2,y=ec.y2}
                        -- The attack event names the weapon it used; only an index on
                        -- this unit's attack list names one candidate. Identical
                        -- weapons stay unnamed instead of guessing.
                        local known,weapon=pcall(function() return wesnoth.get_variable('weapon') end)
                        if known and type(weapon)=='table' then
                            local found=0
                            for wi,w in ipairs(u.attacks or {}) do
                                if tostring(w.name)==tostring(weapon.name) and tostring(w.type)==tostring(weapon.type)
                                    and tostring(w.number)==tostring(weapon.number) and tostring(w.damage)==tostring(weapon.damage) then
                                    found=found==0 and wi or -1
                                end
                            end
                            if found>0 then frame.weapon=found end
                        end
                    end
                end
            end
            emit(frame)
            local context=value.context
            if context and not context.used then
                context.used=true
                if kind=='moveto' and u and value.memory then
                    local C=wesnoth.require '~add-ons/LearningSupport/lua/candidates.lua'
                    C.remember({memory=value.memory,occupied={[ec.x2..','..ec.y2]={id=u.id}}},
                        {kind='move',x=ec.x2,y=ec.y2,tx=x,ty=y})
                end
            end
            if kind~='attack' then after(side) end
        end}
    end
    wesnoth.game_events.add {name='attack end',first_time_only=false,action=function()
        local side=wesnoth.current.side
        if watched[side] then after(side) end
    end}
    -- These transitions are not caused by a watched action: a context captured
    -- before them no longer describes the state the next decision sees. 'unit
    -- placed' is caused by our own recruit/recall, so it must not invalidate.
    for _,kind in ipairs {'side turn','turn refresh'} do
        wesnoth.game_events.add {name=kind,first_time_only=false,action=function()
            for side,_ in pairs(watched) do
                local value=state[side]
                if value and value.context and not value.context.used then
                    emit {type='INVALIDATE',side=side,context=value.context.id,event=kind}
                    value.context=nil
                end
            end
        end}
    end
end
return M
