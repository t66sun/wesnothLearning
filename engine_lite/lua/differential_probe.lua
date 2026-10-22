-- Opt-in native oracle for the offline differential runner. Never loaded by play/training.
local M, battle = {}, nil
local function states(u)
    local out={}
    for _,s in ipairs {'poisoned','slowed','petrified','stunned'} do if u and u.status[s] then out[#out+1]=s end end
    return setmetatable(out,{__array=true})
end
local function result(u)
    return {hp=u and math.max(0,u.hitpoints) or 0,status=states(u)}
end
local function distribution(value)
    local hp={};for k,p in pairs(value.hp_chance) do hp[tostring(k)]=p end
    return {average_hp=value.average_hp,hp_chance=hp,poisoned=value.poisoned,slowed=value.slowed}
end
function M.initialize()
    for _,name in ipairs {'attacker hits','attacker misses','defender hits','defender misses'} do
        local event=name
        wesnoth.game_events.add {name=event,id='learning_diff_'..event:gsub(' ','_'),first_time_only=false,
            action=function()
                if not battle then return end
                local attacking=event:match('^attacker')~=nil
                local a=attacking and battle.a or battle.d
                local d=attacking and battle.d or battle.a
                battle.strikes[#battle.strikes+1]={attacker=a.id,defender=d.id,hit=event:match(' hits$')~=nil,
                    defender_hp=math.max(0,d.hitpoints)}
            end}
    end
end
function M.before(action)
    battle=nil
    if action.kind~='attack' then return end
    local a=assert(wesnoth.units.get(action.x,action.y))
    local d=assert(wesnoth.units.get(action.tx,action.ty))
    local ap,dp,aw,dw=wesnoth.simulate_combat(a,action.weapon,d)
    battle={a=a,d=d,aid=a.id,did=d.id,strikes=setmetatable({},{__array=true}),
        oracle={attacker=distribution(ap),defender=distribution(dp),
            attacker_hit=aw.chance_to_hit/100,defender_hit=dw.chance_to_hit/100}}
end
function M.after()
    if not battle then return nil end
    local out={strikes=battle.strikes,oracle=battle.oracle,
        attacker=result(wesnoth.units.find_on_map{id=battle.aid}[1]),
        defender=result(wesnoth.units.find_on_map{id=battle.did}[1])}
    battle=nil
    return out
end
return M
