-- Engine events are audit facts; only observer DTOs become policy inputs.
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M={}
local serial=0
local contexts={}
local function emit(frame) judge.emit('STOCK',frame) end
function M.capabilities(functions,turn_query)
    emit {type='CAPABILITIES',side=wesnoth.current.side,functions=functions,
        teacher_turn=turn_query,reason='runtime Lua AI surface only; no takeover performed'}
end
function M.context(row,memory)
    serial=serial+1
    contexts[row.side]={id=serial,turn=row.turn,memory=memory}
    emit {type='CONTEXT',id=serial,side=row.side,turn=row.turn,row=row}
end
local function after(side)
    local context=contexts[side]
    if not context or not context.pending or not context.memory then return end
    context.pending=false
    local O=wesnoth.require '~add-ons/LearningSupport/lua/observation.lua'
    local S=wesnoth.require '~add-ons/LearningSupport/lua/spatial.lua'
    emit {type='AFTER',side=side,context=context.id,
        memory_write=S.memory_observation(O.capture(context.memory,side))}
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
            local ec=wesnoth.current.event_context
            local x,y=ec.x1,ec.y1
            local visible=wesnoth.units.find_on_map {x=x,y=y,side=side,
                {'filter_vision',{side=side,visible='yes'}}}
            local u=visible[1]
            local frame={type='ACTION',side=side,turn=wesnoth.current.turn,
                kind=kind=='post advance' and 'advance' or kind,visible=u~=nil,
                context=contexts[side] and contexts[side].id}
            if u then
                frame.unit={x=x,y=y};frame.type_id=u.type
                if kind=='moveto' then
                    frame.unit={x=ec.x2,y=ec.y2};frame.to={x=x,y=y}
                elseif kind=='recruit' or kind=='recall' then frame.to={x=x,y=y}
                elseif kind=='attack' then
                    local target=wesnoth.units.find_on_map {x=ec.x2,y=ec.y2,
                        {'filter_vision',{side=side,visible='yes'}}}
                    frame.visible=target[1]~=nil
                    if frame.visible then frame.target={x=ec.x2,y=ec.y2} end
                    -- Weapon names need not be unique. Missing index remains ambiguous.
                end
            end
            emit(frame)
            local context=contexts[side]
            if context and not context.used then
                context.used=true;context.pending=true
                if kind=='moveto' and u and context.memory then
                    local C=wesnoth.require '~add-ons/LearningSupport/lua/candidates.lua'
                    C.remember({memory=context.memory,occupied={[ec.x2..','..ec.y2]={id=u.id}}},
                        {kind='move',x=ec.x2,y=ec.y2,tx=x,ty=y})
                end
            end
            if kind~='attack' then after(side) end
        end}
    end
    wesnoth.game_events.add {name='attack end',first_time_only=false,action=function()
        if watched[wesnoth.current.side] then after(wesnoth.current.side) end
    end}
end
return M
