-- Timing wrappers used only in the temporary instrumented build. The original
-- functions receive the same arguments and return every value, including nil.
function __timed(label,f)
    assert(type(f)=='function',label)
    return function(...)
        __cost_enter(label)
        local result=table.pack(f(...))
        __cost_leave()
        return table.unpack(result,1,result.n)
    end
end
local function profile_locals(name,source)
    if name=='astra/four.lua' then
        local timed={}
        for _,key in ipairs {'context','recruit','build_threat','attacks','movement'} do
            timed[#timed+1]=key.."=__timed('astra."..key.."',"..key..")"
        end
        local count
        source,count=source:gsub('function M:evaluation%(cfg,data%)',table.concat(timed,'\n')..'\nfunction M:evaluation(cfg,data)')
        assert(count==1,'four-player planner replaced exactly once')
        source,count=source:gsub('local current=rating%(u.x,u.y%)', "__cost_enter('astra.movement_landings')\n        local current=rating(u.x,u.y)")
        assert(count==1,'enter the original landing loop once')
        source,count=source:gsub('if up then\n            local score=uscore%-current', "__cost_leave()\n        if up then\n            local score=uscore-current")
        assert(count==1,'leave after rating all landings')
    end
    return source
end
local function profile_module(name,mod)
    local methods={['observation.lua']={'capture','villages'},['spatial.lua']={'capture','actions','memory_observation'},
        ['candidates.lua']={'generate','execute','remember','diagnostics'},['rewards.lua']={'capture'},
        ['astra/four.lua']={'evaluation'}}
    for _,key in ipairs(methods[name] or {}) do mod[key]=__timed(name..'.'..key,mod[key]) end
end
