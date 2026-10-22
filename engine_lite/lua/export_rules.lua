-- Run explicitly in a native 1.18.8 scope, never from a training observation.
-- This module returns capture data; the calling native capture runner must
-- serialize it as JSON. It does not launch games or write files by itself.
local M={}
local function plain(v)
    if type(v)=='userdata' then return tostring(v) end
    if type(v)~='table' then return v end
    -- WML mixes string attributes with numeric child indices. Export raw
    -- definitions as JSON objects at every level, including the {tag,cfg}
    -- child pairs, so serializers never have to infer a mixed table's shape.
    local result={};for k,value in pairs(v) do result[tostring(k)]=plain(value) end;return result
end
local function children(cfg,tag)
    local result={};for _,child in ipairs(cfg or {}) do if child[1]==tag then result[#result+1]=child[2] end end
    return result
end
local function scripted(cfg)
    for _,child in ipairs(cfg or {}) do
        if child[1]=='lua' or child[1]=='event' or child[1]=='command' then return true end
        if type(child[2])=='table' and scripted(child[2]) then return true end
    end
    return false
end
local display_keys={id=true,name=true,female_name=true,description=true,special_note=true,
    name_inactive=true,female_name_inactive=true,description_inactive=true,halo_image_self=true}
local function only_attributes(cfg,allowed)
    for key in pairs(cfg) do
        if type(key)~='number' and not display_keys[key] and not allowed[key] then return false end
    end
    return true
end
local function simple_adjacent(cfg)
    for _,child in ipairs(cfg) do
        if child[1]~='affect_adjacent' or next(child[2])~=nil then return false end
    end
    return true
end
local function same_rule(actual,expected)
    -- Compare a finite native declaration shape, ignoring only its label.
    if type(actual)~=type(expected) then return false end
    if type(actual)~='table' then return actual==expected end
    for key,value in pairs(actual) do
        if not display_keys[key] and not same_rule(value,expected[key]) then return false end
    end
    for key,value in pairs(expected) do
        if not display_keys[key] and not same_rule(actual[key],value) then return false end
    end
    return true
end
local function standard_heals(cfg)
    local value=tonumber(cfg.value) or 0
    return (value==0 or value==4 or value==8) and
        (cfg.poison=='cured' or cfg.poison=='slowed') and
        cfg.affect_allies==true and cfg.affect_self==false and not cfg.affect_enemies and
        not cfg.cumulative and (simple_adjacent(cfg) or #cfg==1 and
            same_rule(cfg[1],{'affect_adjacent',{{'filter',{{'not',
                {status='dehydration_slowed_by_healer'}}}}}})) and #cfg>0 and
        only_attributes(cfg,{value=true,poison=true,affect_allies=true,affect_self=true,
            affect_enemies=true,cumulative=true})
end
local function standard_terrain_hides(cfg,codes)
    if cfg.affect_self~=true or not only_attributes(cfg,{affect_self=true}) or #cfg~=1 then return nil end
    local filter=cfg[1]
    if filter[1]~='filter' or #filter[2]~=1 or not only_attributes(filter[2],{formula=true}) then return nil end
    local full_moves=filter[2].formula=='if(self.moves = self.max_moves, 1, 0)'
    if filter[2].formula and not full_moves then return nil end
    local location=filter[2][1]
    if location[1]~='filter_location' or #location[2]~=0 or
        not only_attributes(location[2],{terrain=true}) then return nil end
    local pattern=location[2].terrain
    local standard={['*^V*']=true,['*^F*,*^Qhhf,*^Qhuf']=true,['Wo*^*']=true,
        ['S*^*']=true,['*^F*,*^Qhhf,*^Qhuf,D*^*']=true,
        ['Dd^*,Ds^*,Hd^*,Rb^*,Rd^*,Re^*']=true}
    if not standard[pattern] then return nil end
    local result={}
    for _,code in ipairs(codes) do
        -- These native macros use only literal terrain layers and '*'.
        -- A code with no overlay is the same base with an empty overlay layer.
        local layered=code:find('^',1,true) and code or code..'^'
        for part in pattern:gmatch('[^,]+') do
            local lua_pattern=part:gsub('%^','%%^'):gsub('%*','.*')
            if layered:match('^'..lua_pattern..'$') then result[#result+1]=code;break end
        end
    end
    return result,full_moves
end
local function compile_special(tag,cfg,weapon)
    if #cfg>0 then return nil end
    if (tag=='stun' or tag=='firststrike') and only_attributes(cfg,{}) then return tag end
    if tag=='drains' and only_attributes(cfg,{value=true}) then
        local value=tonumber(cfg.value or 50)
        if value and value>=0 and value<=100 and value%1==0 then
            weapon.drain_percent=value;return 'drains'
        end
    elseif tag=='damage' and cfg.apply_to=='opponent' and
        only_attributes(cfg,{apply_to=true,multiply=true}) then
        local value=tonumber(cfg.multiply)
        if value and (value==0.6 or value==0.75) then
            weapon.opponent_damage_percent=math.floor(value*100+0.5);return 'absorb'
        end
    elseif tag=='chance_to_hit' and cfg.apply_to=='opponent' and cfg.active_on=='defense' and
        cfg.cumulative==true and tonumber(cfg.sub)==10 and
        only_attributes(cfg,{apply_to=true,active_on=true,cumulative=true,sub=true}) then
        weapon.defense_cth_sub=10;return 'deflect'
    elseif tag=='attacks' and cfg.apply_to=='opponent' and cfg.active_on=='offense' and
        only_attributes(cfg,{apply_to=true,active_on=true,value=true}) then
        local value=tonumber(cfg.value)
        if value==0 or value==1 then
            weapon.opponent_attacks=math.min(weapon.opponent_attacks or value,value)
            return value==0 and 'swift' or 'shock'
        end
    end
end
local function vanguard_rank(cfg)
    for count=2,6 do
        if same_rule(cfg,{add=25*(count-1),affect_allies=false,affect_self=true,
            {'filter_self',{{'filter_adjacent',{count=count}}}}}) then return count end
    end
end
local function vanguard_group(group)
    local ranks={}
    for _,ability in ipairs(group) do
        if ability[1]=='leadership' then local rank=vanguard_rank(ability[2]);if rank then ranks[rank]=true end end
    end
    for count=2,6 do if not ranks[count] then return false end end
    return true
end
local function initiative(cfg)
    return same_rule(cfg,{affect_allies=true,affect_self=false,
        {'filter_opponent',{{'filter_weapon',{range='melee'}}}}, {'affect_adjacent',{}}})
end
local function compile_ability(tag,cfg,record,codes,group)
    if tag=='regenerate' and cfg.affect_self==true and
        only_attributes(cfg,{affect_self=true,value=true,poison=true}) and
        (cfg.poison==nil or cfg.poison=='cured' or cfg.poison=='slowed') then
        local amount=tonumber(cfg.value)
        local terrain=nil
        if #cfg==1 and cfg[1][1]=='filter_self' then
            local wrapped={affect_self=true,{'filter',cfg[1][2]}}
            terrain=standard_terrain_hides(wrapped,codes)
            if not terrain then return nil,false end
        elseif #cfg>0 then return nil,false end
        if amount and amount>=0 and amount<=150 and amount%1==0 then
            record.regeneration_amount=amount;record.regeneration_poison=cfg.poison or 'none'
            record.regeneration_terrains=terrain;return 'regenerates',true
        end
    elseif tag=='skirmisher' and same_rule(cfg,{affect_self=false,affect_allies=true,{'affect_adjacent',{}}}) then
        return 'distract',true
    elseif tag=='leadership' and same_rule(cfg,{value='(25 * (level - other.level + 1))',
        affect_self=false,cumulative=false,{'affect_adjacent',{{'filter',{formula='level <= other.level'}}}}}) then
        return 'inspire',true
    elseif (tag=='leadership' and vanguard_rank(cfg) or
        tag=='dummy' and cfg.id=='vanguard' and #cfg==0 and only_attributes(cfg,{})) and
        vanguard_group(group) then
        return 'vanguard',true
    elseif tag=='firststrike' then
        if initiative(cfg) then return 'initiative',true end
        if same_rule(cfg,{active_on='defense',affect_allies=true,affect_self=false,
            {'filter_student',{{'filter_weapon',{special_id_active='initiative'}}}}, {'affect_adjacent',{}}}) then
            for _,ability in ipairs(group) do
                if ability[1]=='firststrike' and initiative(ability[2]) then return 'initiative',true end
            end
        end
    elseif tag=='chance_to_hit' and same_rule(cfg,{sub=20,affect_self=false,
        affect_allies=false,affect_enemies=true,cumulative=true,
        {'filter',{{'filter_adjacent',{is_enemy=true}}}},
        {'affect_adjacent',{adjacent='n,s',{'filter',{{'filter_adjacent',{adjacent='n,s',count='2-6',is_enemy=true}}}}}},
        {'affect_adjacent',{adjacent='se,nw',{'filter',{{'filter_adjacent',{adjacent='se,nw',count='2-6',is_enemy=true}}}}}},
        {'affect_adjacent',{adjacent='ne,sw',{'filter',{{'filter_adjacent',{adjacent='ne,sw',count='2-6',is_enemy=true}}}}}}}) then
        return 'diversion',true
    end
    return nil,false
end
function M.capture(options)
    assert(tostring(wesnoth.game_config.version)=='1.18.8','the actual native runtime must be 1.18.8')
    assert(options.source_version=='1.18.8','pin the native runtime to 1.18.8')
    assert(options.source_build_sha256,'hash the actual native build and data manifest')
    assert(options.scope and options.terrain_codes and #options.terrain_codes>0,
        'provide a preprocessed union terrain inventory (including base/overlay combinations)')
    local capture={source_version=options.source_version,source_build_sha256=options.source_build_sha256,
        source_manifest=options.source_manifest,scope=options.scope,required_scopes=options.required_scopes,
        expected_units={},units={},terrains={},raw_definitions={},variations={}}
    for _,code in ipairs(options.terrain_codes) do
        local t=assert(wesnoth.terrain_types[code],'unknown native terrain '..code)
        capture.terrains[code]={id=code,village=t.village or t.gives_income or false,
            castle=t.castle or false,keep=t.keep or false,healing=t.healing or 0,
            concealment=(options.concealment or {})[code] or {}}
    end
    for id,t in pairs(wesnoth.unit_types) do
        local u=wesnoth.units.create{type=id,random_traits=false,random_gender=false,
            generate_name=false,id='rules_capture_'..id,underlying_id=2147483647}
        local record={id=id,scope=options.scope,hp=u.max_hitpoints,moves=u.max_moves,
            vision=u.vision or u.max_moves,level=u.level,cost=t.cost,experience=u.max_experience,
            alignment=u.alignment,advances_to=t.advances_to or {},weapons={},movement={},defense={},
            resistance={},abilities={},unsupported={},approximation_reasons={}}
        if scripted(t.__cfg) then record.unsupported[#record.unsupported+1]='scripted_type_event' end
        for _,code in ipairs(options.terrain_codes) do
            record.movement[code]=u:movement_on(code);record.defense[code]=100-u:defense_on(code)
        end
        for _,kind in ipairs {'blade','pierce','impact','fire','cold','arcane'} do record.resistance[kind]=100-u:resistance_against(kind) end
        for _,immunity in ipairs {'unpoisonable','undrainable','unplagueable'} do
            if u.status[immunity] then record.abilities[#record.abilities+1]=immunity end
        end
        for _,a in ipairs(u.attacks) do
            local weapon={id=a.name,damage=a.damage,strikes=a.number,damage_type=a.type,range=a.range,specials={}}
            for _,specials in ipairs(children(a.__cfg,'specials')) do for _,s in ipairs(specials) do
                local compiled=compile_special(s[1],s[2],weapon)
                local name=compiled or s[2].id or s[1]
                -- plague(TYPE) is a native macro's ID, while its [plague] tag
                -- defines the behavior. Do not map dummy/event-based specials.
                if s[1]=='plague' then
                    if #s[2]==0 and only_attributes(s[2],{type=true}) then name='plague'
                    else record.unsupported[#record.unsupported+1]='plague_parameters:'..name end
                end
                weapon.specials[#weapon.specials+1]=name
                if s[1]=='plague' then
                    local plague_type=s[2].type
                    -- type=null is used by campaigns to suppress the built-in
                    -- corpse and resolve the replacement in an event. It is not
                    -- a unit type and must not become a normal plague rule.
                    if plague_type~=nil and tostring(plague_type)~='null' then
                        weapon.plague_type=plague_type
                    end
                end
                -- Preserve arbitrary filters and conditions explicitly as unsupported.
                if not compiled and (#s[2]>0 or s[2].apply_to or s[2].active_on) then
                    local name=s[2].id or s[1]
                    local standard={poison=true,slow=true,drains=true,magical=true,marksman=true,charge=true,
                        firststrike=true,berserk=true,swarm=true,plague=true,petrifies=true,backstab=true}
                    if standard[name] then
                        record.approximation_reasons[#record.approximation_reasons+1]='standard_weapon_conditions:'..weapon.id..':'..name
                    else record.unsupported[#record.unsupported+1]='conditional_weapon:'..weapon.id..':'..name end
                end
            end end
            record.weapons[#record.weapons+1]=weapon
        end
        for _,abilities in ipairs(children(u.__cfg,'abilities')) do for _,a in ipairs(abilities) do
            local compiled,handled=compile_ability(a[1],a[2],record,options.terrain_codes,abilities)
            local name=compiled or a[2].id or a[1]
            if a[1]=='heals' then
                if standard_heals(a[2]) then
                    name=a[2].poison=='cured' and 'curing' or 'healing'
                    record.healing_amount=math.max(record.healing_amount or 0,tonumber(a[2].value) or 0)
                    if record.healing_poison~='cured' then record.healing_poison=a[2].poison end
                    if not simple_adjacent(a[2]) then record.healing_excluded_status='dehydration_slowed_by_healer' end
                    if a[2].poison=='cured' and simple_adjacent(a[2]) then record.curing_unfiltered=true end
                else record.unsupported[#record.unsupported+1]='heals_parameters:'..name end
            elseif a[1]=='illuminates' then
                local value=tonumber(a[2].value)
                if #a[2]==0 and ((value==25 and tonumber(a[2].max_value)==25) or
                    (value==-25 and tonumber(a[2].min_value)==-25)) and not a[2].cumulative and a[2].affect_self==true and
                    only_attributes(a[2],{value=true,max_value=true,min_value=true,cumulative=true,affect_self=true,halo_image=true}) then
                    name='illuminates';record.illumination=value
                else record.unsupported[#record.unsupported+1]='illuminates_parameters:'..name end
            elseif a[1]=='hides' and name~='nightstalk' then
                local terrain_codes,full_moves=standard_terrain_hides(a[2],options.terrain_codes)
                if terrain_codes then
                    if name~='ambush' and name~='submerge' and name~='concealment' then name='concealment' end
                    record.concealment_terrains=record.concealment_terrains or {}
                    for _,code in ipairs(terrain_codes) do record.concealment_terrains[#record.concealment_terrains+1]=code end
                    if full_moves then record.concealment_requires_full_moves=true end
                    handled=true
                else record.unsupported[#record.unsupported+1]='hides_parameters:'..name end
            elseif name=='feeding' then
                if a[1]~='dummy' or #a[2]>0 or not only_attributes(a[2],{}) then
                    record.unsupported[#record.unsupported+1]='feeding_parameters'
                end
            end
            record.abilities[#record.abilities+1]=name
            if #a[2]>0 and not handled then
                local standard={skirmisher=true,teleport=true,ambush=true,submerge=true,concealment=true,nightstalk=true,
                    heals=true,healing=true,curing=true,regenerates=true,regeneration=true,
                    leadership=true,illuminates=true,steadfast=true}
                if standard[name] then record.approximation_reasons[#record.approximation_reasons+1]='standard_ability_conditions:'..name
                else record.unsupported[#record.unsupported+1]='conditional_ability:'..name end
            end
        end end
        capture.units[id]=record;capture.expected_units[#capture.expected_units+1]=id
        capture.raw_definitions[id]=plain(t.__cfg)
        local variations={};for name,v in pairs(t.variations) do variations[name]=plain(v.__cfg) end
        capture.variations[id]=variations
    end
    table.sort(capture.expected_units)
    return capture
end
return M
