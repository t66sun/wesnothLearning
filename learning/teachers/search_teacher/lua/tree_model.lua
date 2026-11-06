local G=wesnoth.require '~add-ons/search_teacher/lua/geometry.lua'
local S=wesnoth.require '~add-ons/search_teacher/lua/state.lua'
local A=wesnoth.require '~add-ons/search_teacher/lua/actions.lua'
local T={}
local function flag(v) return v and 1 or 0 end
function T.key(node)
    if node.identity then return node.identity end
    local s=node.state;local rows={s.side,s.turn,node.used or 0,flag(s.leaf_only)};local units={}
    for id in pairs(s.units) do units[#units+1]=id end;table.sort(units)
    for _,id in ipairs(units) do local u=s.units[id]
        rows[#rows+1]=table.concat({id,u.side,u.x,u.y,u.hp,u.moves,u.attacks_left,flag(u.slow),flag(u.poison)},',')
    end
    local villages={};for k in pairs(s.owners) do villages[#villages+1]=k end;table.sort(villages)
    for _,k in ipairs(villages) do rows[#rows+1]=k..'='..s.owners[k] end
    for side=1,s.players do rows[#rows+1]=(s.gold[side] or 0)..'/'..(s.adjustment[side] or 0) end
    node.identity=table.concat(rows,';');return node.identity
end
function T.create(state,root_actions,config,expired)
    local model={};local root={state=state,used=0,choices=root_actions}
    function model.key(node) return T.key(node) end
    function model.terminal(node) return node.state.leaf_only or node.state.turn>node.state.max_turns end
    function model.maximizing(node) return not state.enemies[state.root_side][node.state.side] end
    function model.evaluate(node,side)
        return math.floor(S.value(node.state,side or state.root_side)*1000+.5)
    end
    function model.actions(node)
        if not node.choices then
            local cfg=G.copy(config);cfg.attacks_only=true
            cfg.width=node.state.side==state.root_side and (config.width or 6) or (config.reply_width or 3)
            node.choices=A.generate(node.state,cfg,expired,false)
        end
        return node.choices
    end
    function model.apply(node,action,rng)
        local side=node.state.side;local next_state=S.apply(node.state,action,rng)
        if action.kind=='move' then
            next_state.adjustment[side]=(next_state.adjustment[side] or 0)+action.score*(config.position_weight or .8)
        end
        local used=action.kind=='end_turn' and 0 or (node.used or 0)+1
        if used>=(config.actions_per_side or 2) and not next_state.leaf_only then
            next_state=S.apply(next_state,{kind='end_turn'});used=0
        end
        return {state=next_state,used=used}
    end
    return root,model
end
return T
