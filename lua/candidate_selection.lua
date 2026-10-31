local M={}
local function class(a)
    return (a.kind=='attack' or a.kind=='move_attack') and 'combat' or a.kind
end
local function identity(a)
    local fields={}
    for _,key in ipairs {'kind','x','y','tx','ty','ex','ey','type','weapon','full'} do
        fields[#fields+1]=key..'='..tostring(a[key])
    end
    return table.concat(fields,'|')
end
local function group(a)
    return a.kind=='recruit' and a.type or tostring(a.x)..','..tostring(a.y)
end
function M.select(pool)
    local ranked={};local seen={}
    for _,a in ipairs(pool) do ranked[#ranked+1]=a end
    table.sort(ranked,function(a,b)
        if (a.rule or 0)~=(b.rule or 0) then return (a.rule or 0)>(b.rule or 0) end
        if (a._gain or 0)~=(b._gain or 0) then return (a._gain or 0)>(b._gain or 0) end
        return identity(a)<identity(b)
    end)
    local classes={combat={},recruit={},move={}}
    local unique={}
    for _,a in ipairs(ranked) do
        local key=identity(a);local bucket=classes[class(a)]
        if bucket and not seen[key] then
            seen[key]=true;bucket[#bucket+1]=a;unique[#unique+1]=a
        end
    end
    local selected={};local used={}
    local function take(a)
        selected[#selected+1]=a;used[identity(a)]=true
    end
    for _,kind in ipairs {'combat','recruit','move'} do
        local bucket=classes[kind];local count=0
        -- One ranked action per actor/recruit type per pass preserves diversity.
        while count<12 do
            local groups={};local added=false
            for _,a in ipairs(bucket) do
                local key=group(a)
                if not used[identity(a)] and not groups[key] and count<12 then
                    take(a);groups[key]=true;count=count+1;added=true
                end
            end
            if not added then break end
        end
    end
    for _,a in ipairs(unique) do
        if #selected>=36 then break end
        if not used[identity(a)] then take(a) end
    end
    return selected
end
return M
