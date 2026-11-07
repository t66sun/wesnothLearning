local G={}
function G.key(x,y) return x*1000+y end
function G.distance(a,b)
    local q=b.x-a.x;local r=b.y-a.y+math.floor((a.x-1)/2)-math.floor((b.x-1)/2)
    return math.max(math.abs(q),math.abs(r),math.abs(q+r))
end
function G.neighbors(x,y)
    local d=x%2==1 and -1 or 1
    return {{x,y-1},{x,y+1},{x-1,y},{x+1,y},{x-1,y+d},{x+1,y+d}}
end
function G.copy(t)
    local result={};for k,v in pairs(t) do result[k]=v end;return result
end
function G.random(seed)
    local state=math.max(1,math.floor(seed or 1)%2147483647)
    return function() state=state*16807%2147483647;return state/2147483647 end
end
return G
