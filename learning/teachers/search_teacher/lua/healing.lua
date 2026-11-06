local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local H={}
function H.poison_mode(value) return value=='cured' and 2 or value=='slowed' and 1 or 0 end
-- Standard six-faction healing, on a copied visible position. Rest healing is omitted.
function H.start(s)
    for _,u in pairs(s.units) do if u.hp>0 and not u.petrified and not u.unhealable then
        local own=u.side==s.side;local amount,poison=0,0
        if own then
            amount=math.max(s.villages[G.key(u.x,u.y)] and 8 or 0,u.regenerates or 0)
            poison=s.villages[G.key(u.x,u.y)] and 2 or (u.regeneration_poison or 0)
        end
        for _,h in pairs(s.units) do
            if h.id~=u.id and h.hp>0 and not h.petrified and not s.enemies[u.side][h.side]
                and not s.enemies[s.side][h.side] and G.distance(u,h)==1 then
                if h.side==s.side then
                    amount=math.max(amount,h.healing or 0)
                    poison=math.max(poison,h.healing_poison or 0)
                else poison=math.max(poison,math.min(1,h.healing_poison or 0)) end
            end
        end
        if u.poison then
            if poison==2 then u.poison=false
            elseif own and poison==0 then u.hp=math.max(1,u.hp-8) end
        else u.hp=math.min(u.max_hp,u.hp+amount) end
    end end
end
return H
