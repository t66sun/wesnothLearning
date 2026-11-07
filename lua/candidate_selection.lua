local M={}
-- Preserve generated primary moves, then fill per-class reserves within the
-- 36 actionable slots. Combat gets the largest remaining share; recruiting
-- keeps type diversity across the six reserved entries.
local LIMIT={combat=28,recruit=6,move=2}
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
local function weapon_group(a)
    return a.x..','..a.y..':'..a.tx..','..a.ty..':'..(a.ex or '')..','..(a.ey or '')
end
local function retain_weapons(selected,combat,used,dominates,capacity,collect_support)
    local count=0
    for _,a in ipairs(selected) do if class(a)=='combat' then count=count+1 end end
    -- Reserve one forecast per retained combat slot. Each excluded challenger
    -- spends one spare call regardless of whether it wins the comparison.
    local spare=capacity-count
    if spare<=0 or count==0 or count==#combat then return end
    local groups={}
    for slot,a in ipairs(selected) do
        if class(a)=='combat' then
            local key=weapon_group(a)
            local slots=groups[key] or {}
            slots[#slots+1]=slot;groups[key]=slots
        end
    end
    for _,a in ipairs(combat) do
        if not used[a] then
            local slots=groups[weapon_group(a)]
            if slots then
                for _,slot in ipairs(slots) do
                    if dominates(a,selected[slot]) then
                        if collect_support then a._coverage_kind='weapon_replacement' end
                        selected[slot]=a;break
                    end
                end
                spare=spare-1
                if spare==0 then break end
            end
        end
    end
end
function M.select(pool,dominates,capacity,collect_support)
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
        selected[#selected+1]=a;used[a]=true
    end
    -- Primary full moves are already budgeted/probed once per actor. Preserve
    -- them when more combat landings become available instead of losing actors
    -- in the final refill. The remaining slots still prefer combat.
    for _,a in ipairs(unique) do
        if a._primary_move and #selected<36 then take(a) end
    end
    for _,kind in ipairs {'recruit','combat','move'} do
        local bucket=classes[kind];local limit=LIMIT[kind];local count=0
        for _,a in ipairs(selected) do if class(a)==kind then count=count+1 end end
        -- One ranked action per actor/recruit type per pass preserves diversity.
        while count<limit and #selected<36 do
            local groups={};local added=false
            for _,a in ipairs(bucket) do
                local key=group(a)
                if not used[a] and not groups[key] and count<limit and #selected<36 then
                    take(a);groups[key]=true;count=count+1;added=true
                end
            end
            if not added then break end
        end
    end
    for _,a in ipairs(unique) do
        if #selected>=36 then break end
        if not used[a] then take(a) end
    end
    if dominates then retain_weapons(selected,classes.combat,used,dominates,capacity,collect_support) end
    return selected
end
return M
