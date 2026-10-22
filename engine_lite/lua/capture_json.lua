-- JSON writer for the native rule capture boundary. Raw WML child indices have
-- already been converted to string keys by export_rules.lua.
local M={}
local arrays={expected_units=true,required_scopes=true,advances_to=true,weapons=true,
    abilities=true,unsupported=true,approximation_reasons=true,specials=true,healing_effects=true,
    concealment_terrains=true,concealment=true,regeneration_terrains=true}
local escapes={['"']='\\"',['\\']='\\\\',['\b']='\\b',['\f']='\\f',['\n']='\\n',['\r']='\\r',['\t']='\\t'}
local function quote(value)
    return '"'..value:gsub('[%z\1-\31\\"]',function(c)
        return escapes[c] or string.format('\\u%04x',c:byte())
    end)..'"'
end
function M.encode(value,field)
    local kind=type(value)
    if kind=='nil' then return 'null' end
    if kind=='boolean' then return value and 'true' or 'false' end
    if kind=='number' then
        assert(value==value and math.abs(value)<math.huge,'nonfinite capture value')
        return tostring(value)
    end
    if kind=='string' or kind=='userdata' then return quote(tostring(value)) end
    assert(kind=='table','unsupported JSON capture value '..kind)
    local numeric,count=true,0
    for key in pairs(value) do
        count=count+1
        if type(key)~='number' or key<1 or key%1~=0 then numeric=false end
    end
    local result={}
    if arrays[field] or (numeric and count>0 and count==#value) then
        for _,item in ipairs(value) do result[#result+1]=M.encode(item) end
        return '['..table.concat(result,',')..']'
    end
    local keys={};for key in pairs(value) do keys[#keys+1]=key end
    table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
    for _,key in ipairs(keys) do result[#result+1]=quote(tostring(key))..':'..M.encode(value[key],key) end
    return '{'..table.concat(result,',')..'}'
end
return M
