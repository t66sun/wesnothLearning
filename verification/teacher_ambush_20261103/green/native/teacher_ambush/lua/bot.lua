-- Fixed native execution fixture: a legal one-hex move reveals a forest Wose.
local teacher=wesnoth.dofile '~add-ons/teacher_ambush/lua/four.lua'
local AH=wesnoth.require 'ai/lua/ai_helper.lua'
local judge=wesnoth.require '~add-ons/arena_runtime/runtime.lua'
local M={}

function M:evaluation(cfg,data)
    if data.done then return 0 end
    if not data.initialized then
        wesnoth.units.to_map{type='Drake Fighter',id='actor',side=1,x=4,y=3,random_traits=false}
        wesnoth.units.to_map{type='Wose',id='ambusher',side=2,x=2,y=3,random_traits=false}
        wesnoth.units.to_map{type='Orcish Grunt',id='target',side=2,x=4,y=4,random_traits=false}
        data.initialized=true
    end
    data.plan={kind='combat',id='actor',x=4,y=3,tx=3,ty=4,enemy='target',weapon=1}
    return 100000
end

function M:execution(cfg,data)
    local actor=wesnoth.units.find_on_map{id='actor'}[1]
    local visible_before={}
    for _,u in ipairs(AH.get_attackable_enemies()) do visible_before[u.id]=true end
    judge.emit('TEACHER_BEFORE',{checked=ai.check_move(actor,3,4).ok,
        ambusher_visible=not not visible_before.ambusher})
    local move,attack=ai.move,ai.attack
    local attacks=0
    ai.move=function(...)
        local result=move(...)
        judge.emit('TEACHER_MOVE',{status=result.status,ok=result.ok,
            changed=result.gamestate_changed,x=actor.x,y=actor.y})
        return result
    end
    ai.attack=function(...)
        attacks=attacks+1
        return attack(...)
    end
    teacher:execution(cfg,data)
    ai.move,ai.attack=move,attack
    local visible_after={}
    for _,u in ipairs(AH.get_attackable_enemies()) do visible_after[u.id]=true end
    judge.emit('TEACHER_AFTER',{attacks=attacks,x=actor.x,y=actor.y,
        ambusher_visible=not not visible_after.ambusher})
    data.done=true
    judge.finish('turn_limit')
end

return M
