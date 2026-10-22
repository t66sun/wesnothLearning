-- Deterministic API doubles: this file never starts or controls Wesnoth.
fixture={clock=0,hidden={},visible={},own={},owners={},fog={},calls={},leaders={}}
local F=fixture
local function unit(id,side,x,y,leader)
    local u={id=id,side=side,type='Fighter',x=x,y=y,canrecruit=leader,hitpoints=40,max_hitpoints=40,
        moves=4,max_moves=4,attacks_left=1,attacks={{name='sword',damage=5,number=3,type='blade',range='melee'}},status={}}
    function u:defense_on(_) return 50 end
    function u:movement_on(_) return 1 end
    function u:resistance_against(_) return 100 end
    function u:clone()
        local c={};for k,v in pairs(self) do c[k]=v end;return c
    end
    return u
end
F.own={unit('leader',1,1,1,true),unit('soldier',1,2,1,false)}
F.visible={F.own[1],F.own[2],unit('enemy',2,3,1,true),unit('ally',3,1,2,true)}
F.leaders={[1]=true,[2]=true,[3]=true,[4]=true}
F.teams={1,2,1,2}
wesnoth={current={side=1,turn=1,map=setmetatable({width=8,height=6}, {__index=function(_,k) if type(k)=='table' and k[1]==4 and k[2]==3 then return 'Ch' end return 'Gg' end})},
    unit_types={Fighter={cost=14}},wml_actions={},game_events={}}
function wesnoth.commit() end
wesnoth.sides={{gold=100,recruit={'Fighter'},total_income=4,controller='ai'},{gold=100,controller='ai'},{gold=100,controller='ai'},{gold=100,controller='ai'}}
function wesnoth.sides.is_enemy(a,b) return F.teams[a]~=F.teams[b] end
function wesnoth.sides.is_fogged(_,x,y) return F.fog[x..','..y] or false end
function wesnoth.sides.is_shrouded() return false end
wesnoth.units={}
function wesnoth.units.find_on_map(filter)
    if filter.canrecruit then
        return F.leaders[filter.side] and {{hitpoints=40}} or {}
    elseif filter.side then
        assert(filter.side==1,'unexpected private side-unit query')
        return F.own
    elseif F.judge and not filter[1] then
        return F.visible
    else
        assert(filter[1][1]=='filter_vision','unrestricted unit query')
        assert(filter[1][2].side==1 and filter[1][2].visible=='yes','wrong vision')
        return F.visible
    end
end
function wesnoth.units.create(cfg) return unit('recruit',cfg.side,cfg.x,cfg.y,false) end
function wesnoth.units.clone(u) return u:clone() end
function wesnoth.units.get(x,y)
    for _,u in ipairs(F.visible) do if u.x==x and u.y==y then return u end end
end
wesnoth.map={}
function wesnoth.map.distance_between(x,y,tx,ty) return math.abs(x-tx)+math.abs(y-ty) end
function wesnoth.map.find(filter) return filter.terrain and {{1,3}} or {{2,2},{4,4}} end
function wesnoth.map.get_owner(p)
    assert(not F.fog[p[1]..','..p[2]],'hidden village owner queried')
    return F.owners[p[1]..','..p[2]] or 0
end
wesnoth.paths={find_reach=function(u,cfg)
    assert(cfg.viewing_side==1 and cfg.ignore_visibility==false,'visibility-aware path required')
    return {{u.x,u.y,u.moves},{2,2,2},{3,2,1}}
end}
wesnoth.schedule={get_time_of_day=function() return {lawful_bonus=25} end}
function wesnoth.ms_since_init() return F.clock end
function wesnoth.simulate_combat()
    return {average_hp=30,hp_chance={[0]=.05}},{average_hp=20,hp_chance={[0]=.25}}
end
local function action(name)
    return function(...) F.calls[#F.calls+1]=name;return {ok=true} end
end
ai={check_recruit=function() return {ok=true} end,check_move=function() return {ok=true} end,
    check_attack=function() return {ok=true} end,recruit=action('recruit'),move=action('move'),
    move_full=action('move_full'),attack=action('attack')}
function wesnoth.wml_actions.kill(cfg) F.leaders[cfg.side]=false end
function wesnoth.wml_actions.endlevel(_) F.ended=true end
function wesnoth.game_events.add(_) end
wml={variables={}}
function std_print(_) end
return F
