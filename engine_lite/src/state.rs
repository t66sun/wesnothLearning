use crate::{combat,model::*};
use serde::{Deserialize,Serialize};
use serde_json::{json,Value};
use std::{cmp::Reverse,collections::{BTreeMap,BTreeSet,BinaryHeap},sync::Arc};

/// `expected_damage_v1` poison: one six-HP tick at the poisoned unit's own turn.
pub const POISON_TICK: i32 = 6;

#[derive(Clone,Serialize,Deserialize)]
pub struct Game {
    pub rules: Arc<Rules>,
    pub spec: GameSpec,
    pub units: Vec<Unit>,
    pub sides: Vec<Side>,
    pub village_owner: Vec<usize>,
    pub knowledge: Vec<Knowledge>,
    pub turn: u32,
    pub current: usize,
    pub revision: u64,
    pub next_id: u64,
    pub finished: bool,
    pub truncated: bool,
    pub winner: Option<String>,
    pub exploration_seen: BTreeMap<String,BTreeSet<usize>>,
    pub exploration_earned: BTreeMap<String,f64>,
}
impl Game {
    pub fn new(rules:Arc<Rules>,spec:GameSpec)->Result<Self,String> {
        rules.validate()?;
        let n=spec.width.checked_mul(spec.height).ok_or("invalid dimensions")?;
        if spec.width==0 || spec.height==0 || spec.terrain.len()!=n || spec.sides.len()<2 || spec.max_turns==0 {
            return Err("invalid map, sides or turn limit".into());
        }
        for t in &spec.terrain {if !rules.terrains.contains_key(t){return Err(format!("unknown terrain {t}"));}}
        let mut occupied=BTreeSet::new();let mut ids=BTreeSet::new();
        for (i,s) in spec.sides.iter().enumerate() {
            if s.id!=i+1 || s.team.is_empty() {return Err("sides must be consecutive 1-based IDs with nonempty teams".into());}
            for r in &s.recruit {if !rules.units.contains_key(r) {return Err(format!("unknown recruit {r}"));}}
            if !spec.units.iter().any(|u|u.side==s.id && u.leader && u.hp>0){return Err(format!("side {} has no starting leader",s.id));}
        }
        let mut needed:Vec<String>=spec.units.iter().map(|u|u.unit_type.clone()).chain(spec.sides.iter().flat_map(|s|s.recruit.clone())).collect();
        let mut checked=BTreeSet::new();
        while let Some(id)=needed.pop(){
            if !checked.insert(id.clone()){continue;}
            let t=rules.units.get(&id).ok_or_else(||format!("missing type {id}"))?;
            if !t.unsupported.is_empty(){return Err(format!("type {id} has unimplemented declarations: {}",t.unsupported.join(", ")));}
            needed.extend(t.advances_to.clone());needed.extend(t.weapons.iter().filter_map(|w|w.plague_type.clone()));
        }
        for u in &spec.units {
            let t=rules.units.get(&u.unit_type).ok_or_else(||format!("unknown type {}",u.unit_type))?;
            if u.pos>=n || u.side==0 || u.side>spec.sides.len() || !occupied.insert(u.pos) || !ids.insert(&u.id)
                || u.hp<=0 || u.hp>u.max_hp(&rules) || u.moves>u.max_moves(&rules) || u.max_hp(&rules)<=0 || u.max_xp(&rules)==0 || u.attacks_left>1 {
                return Err(format!("invalid unit {}",u.id));
            }
            if !spec.allow_approximate && (!t.unsupported.is_empty() || !t.abilities.is_empty() || t.weapons.iter().any(|w|!w.specials.is_empty())) {
                return Err(format!("{} requires explicit allow_approximate; consult coverage.json",u.unit_type));
            }
        }
        // The current combat/economy/vision contract has documented approximations even
        // for ordinary units. Never label a game an exact native-equivalent simulation.
        if !spec.allow_approximate {return Err(format!("{ENGINE_VERSION} requires allow_approximate=true; native differential acceptance is pending"));}
        let mut owner=vec![0;n];
        for (&p,&s) in &spec.village_owner {
            if p>=n || s>spec.sides.len() || !rules.terrains[&spec.terrain[p]].village {return Err("invalid village owner".into());}
            owner[p]=s;
        }
        let count=spec.sides.len();
        let mut g=Self{rules,units:spec.units.clone(),sides:spec.sides.clone(),village_owner:owner,
            knowledge:vec![Knowledge{visible:vec![false;n],explored:vec![false;n],terrain:vec![None;n],..Knowledge::default()};count],
            spec,turn:1,current:1,revision:0,next_id:1,finished:false,truncated:false,winner:None,
            exploration_seen:BTreeMap::new(),exploration_earned:BTreeMap::new()};
        g.update_visibility();g.update_exploration(true);Ok(g)
    }
    pub fn adjacent(&self,p:usize)->Vec<usize>{neighbors(p,self.spec.width,self.spec.height)}
    pub fn enemy(&self,a:usize,b:usize)->bool {self.sides[a-1].team!=self.sides[b-1].team}
    pub fn side_check(&self,s:usize)->Result<(),String>{if s==0 || s>self.sides.len(){Err("invalid side".into())}else{Ok(())}}
    pub fn unit(&self,id:&str)->Option<usize>{self.units.iter().position(|u|u.id==id && u.hp>0)}
    fn concealed(&self,u:&Unit,viewer:usize)->bool {
        if !self.enemy(u.side,viewer) || u.status.contains("petrified") {return false;}
        if self.units.iter().any(|f|f.hp>0 && !self.enemy(f.side,viewer) && self.adjacent(u.pos).contains(&f.pos)){return false;}
        let t=&self.rules.units[&u.unit_type];let tile=&self.rules.terrains[&self.spec.terrain[u.pos]];
        (t.concealment_terrains.contains(&self.spec.terrain[u.pos]) &&
            (!t.concealment_requires_full_moves || u.moves==u.max_moves(&self.rules))) ||
            t.abilities.iter().any(|a|tile.concealment.contains(a)) ||
            (t.abilities.contains("nightstalk") && self.rules.lawful_bonus[(self.turn as usize-1)%self.rules.lawful_bonus.len()]<0)
    }
    fn skirmisher_at(&self,u:&Unit,pos:usize,context:&[Unit])->bool {
        self.rules.units[&u.unit_type].abilities.contains("skirmisher") || context.iter().any(|source|
            source.hp>0 && source.id!=u.id && !source.status.contains("petrified") &&
            !self.enemy(source.side,u.side) && self.adjacent(pos).contains(&source.pos) &&
            self.rules.units[&source.unit_type].abilities.contains("distract"))
    }
    pub fn public_units(&self,s:usize)->Vec<Unit> {
        let mut public:Vec<Unit>=self.units.iter().filter(|u|u.hp>0 && (u.side==s || self.knowledge[s-1].visible[u.pos] && !self.concealed(u,s))).cloned().collect();
        // Native unit.status exposes intrinsic type immunities as public flags.
        // Keep them derived on the view so advancing or changing type cannot
        // leave a stale static immunity on the underlying unit.
        for u in &mut public {
            if let Some(t)=self.rules.units.get(&u.unit_type) {
                for flag in ["undrainable","unplagueable","unpoisonable"] {
                    if t.abilities.contains(flag) {u.status.insert(flag.to_string());}
                }
            }
        }
        public
    }
    pub fn update_visibility(&mut self) {
        let n=self.spec.terrain.len();let count=self.sides.len();let mut raw=vec![vec![false;n];count];
        for u in self.units.iter().filter(|u|u.hp>0) {
            let t=&self.rules.units[&u.unit_type];let mut dist=vec![u32::MAX;n];let mut queue=BinaryHeap::new();
            dist[u.pos]=0;queue.push((Reverse(0u32),u.pos));
            while let Some((Reverse(d),p))=queue.pop() {
                if d!=dist[p] {continue;}raw[u.side-1][p]=true;
                for q in self.adjacent(p) {
                    // Separate native vision_costs/jamming are not implemented yet.
                    let cost=t.movement[&self.spec.terrain[q]].max(1);
                    if d.saturating_add(cost)<=t.vision && d+cost<dist[q] {dist[q]=d+cost;queue.push((Reverse(d+cost),q));}
                }
            }
        }
        let previous:Vec<Vec<bool>>=self.knowledge.iter().map(|k|k.explored.clone()).collect();
        for i in 0..count {
            let mut seen=raw[i].clone();let mut explored=previous[i].clone();
            for j in 0..count {
                if i!=j && !self.enemy(i+1,j+1) {
                    if self.sides[i].share_view {for p in 0..n {seen[p]|=raw[j][p];}}
                    if self.sides[i].share_maps {for p in 0..n {explored[p]|=previous[j][p] || raw[j][p];}}
                }
            }
            for p in 0..n {
                explored[p]|=seen[p] || !self.sides[i].shroud;
                let visible=explored[p] && (seen[p] || !self.sides[i].fog);
                self.knowledge[i].explored[p]=explored[p];self.knowledge[i].visible[p]=visible;
                if explored[p] {self.knowledge[i].terrain[p]=Some(self.spec.terrain[p].clone());}
                if visible && self.rules.terrains[&self.spec.terrain[p]].village {
                    self.knowledge[i].villages.insert(p,(self.village_owner[p],self.turn));
                }
            }
            let visible_units=self.public_units(i+1);
            // Remove stale sightings on an observed empty tile; never peek at hidden enemies.
            let currently:BTreeSet<String>=visible_units.iter().map(|u|u.id.clone()).collect();
            let visible_tiles=self.knowledge[i].visible.clone();
            self.knowledge[i].enemies.retain(|id,v|v.unit.as_ref().is_some_and(|u|!visible_tiles[u.pos] || currently.contains(id)));
            let enemies:Vec<Unit>=visible_units.into_iter().filter(|u|self.enemy(i+1,u.side)).collect();
            for u in enemies {
                self.knowledge[i].enemies.insert(u.id.clone(),SeenUnit{unit:Some(u),turn:self.turn});
            }
        }
    }
    pub fn observe(&self,s:usize)->Result<Value,String>{
        self.side_check(s)?;let k=&self.knowledge[s-1];
        let public=self.public_units(s);
        let sides:Vec<Value>=self.sides.iter().map(|other|json!({"id":other.id,"team":other.team,
            "eliminated":other.eliminated,"gold":if other.id==s{Some(other.gold)}else{None},
            "base_income":if other.id==s{Some(other.base_income)}else{None},
            "total_income":if other.id==s{Some(self.public_income(s))}else{None},
            "fog":other.fog,"shroud":other.shroud,"share_view":other.share_view,"share_maps":other.share_maps,
            "recruit":if other.id==s{Some(&other.recruit)}else{None}})).collect();
        Ok(json!({"engine_id":ENGINE_VERSION,"rules_version":self.rules.rules_version,"rules_hash":self.rules.source_hash,
            "rng_version":RNG_VERSION,"combat_version":COMBAT_VERSION,"approximate":true,"side":s,"current_side":self.current,"turn":self.turn,
            "width":self.spec.width,"height":self.spec.height,"terrain":k.terrain,"visible":k.visible,
            "explored":k.explored,"units":public,"sides":sides,"villages":k.villages,
            "last_seen":k.enemies,"finished":self.finished,"truncated":self.truncated,"winner":self.winner}))
    }
    /// Public-information Dijkstra. Unknown terrain uses an explicit optimistic
    /// cost of one; execution stops when newly revealed terrain blocks the intent.
    pub fn reach(&self,u:&Unit,s:usize)->(Vec<u32>,Vec<usize>) {
        let n=self.spec.terrain.len();let mut dist=vec![u32::MAX;n];let mut prev=vec![usize::MAX;n];
        let t=&self.rules.units[&u.unit_type];let public=self.public_units(s);
        let occupied:BTreeMap<usize,&Unit>=public.iter().map(|x|(x.pos,x)).collect();
        let zoc:BTreeSet<usize>=public.iter().filter(|e|self.enemy(e.side,u.side) && self.rules.units[&e.unit_type].level>0 && !e.status.contains("petrified") && !e.status.contains("stunned"))
            .flat_map(|e|self.adjacent(e.pos)).collect();
        let mut queue=BinaryHeap::new();dist[u.pos]=0;prev[u.pos]=u.pos;queue.push((Reverse(0),u.pos));
        if u.status.contains("petrified") {return (dist,prev);}
        while let Some((Reverse(d),p))=queue.pop() {
            if d!=dist[p] || p!=u.pos && zoc.contains(&p) && !self.skirmisher_at(u,p,&public) {continue;}
            let mut next=self.adjacent(p);
            if t.abilities.contains("teleport") && self.knowledge[s-1].villages.get(&p).is_some_and(|v|v.0==u.side) {
                next.extend(self.knowledge[s-1].villages.iter().filter(|(_,v)|v.0==u.side).map(|(&q,_)|q));
            }
            for q in next {
                if occupied.get(&q).is_some_and(|o|self.enemy(o.side,u.side)) {continue;}
                    let teleport=!self.adjacent(p).contains(&q);
                    let mut cost=if teleport{1}else{self.knowledge[s-1].terrain[q].as_ref().map(|code|t.movement[code]).unwrap_or(1).max(1)};
                if u.status.contains("slowed") {cost=cost.saturating_mul(2);}
                let nd=d.saturating_add(cost);
                if nd<=u.moves && nd<dist[q] {dist[q]=nd;prev[q]=p;queue.push((Reverse(nd),q));}
            }
        }
        (dist,prev)
    }
    fn castle_slots(&self,s:usize)->BTreeSet<usize> {
        let mut result=BTreeSet::new();let k=&self.knowledge[s-1];
        for u in self.units.iter().filter(|u|u.hp>0 && u.side==s && u.leader) {
            if !self.rules.terrains[&self.spec.terrain[u.pos]].keep {continue;}
            let mut todo=vec![u.pos];let mut seen=BTreeSet::new();
            while let Some(p)=todo.pop() {
                if !seen.insert(p){continue;}
                if k.terrain[p].as_ref().is_some_and(|t|self.rules.terrains[t].castle || self.rules.terrains[t].keep) {
                    result.insert(p);todo.extend(self.adjacent(p));
                }
            }
        }
        let occupied:BTreeSet<usize>=self.public_units(s).iter().map(|u|u.pos).collect();
        result.retain(|p|!occupied.contains(p));result
    }
    pub fn legal_actions(&self,s:usize)->Result<Vec<Action>,String> {
        self.side_check(s)?;
        if self.finished || self.current!=s {return Ok(vec![]);}
        let public=self.public_units(s);let occupied:BTreeSet<usize>=public.iter().map(|u|u.pos).collect();
        let mut actions=vec![Action::EndTurn];
        for u in public.iter().filter(|u|u.side==s && !u.status.contains("petrified")) {
            if u.moves>0 {let (d,_)=self.reach(u,s);
                for (p,&cost) in d.iter().enumerate(){if p!=u.pos && cost<=u.moves && !occupied.contains(&p){
                    actions.push(Action::Move{unit:u.id.clone(),to:p,full:false});
                }}
            }
            if u.attacks_left>0 {
                for e in public.iter().filter(|e|self.enemy(s,e.side) && self.adjacent(u.pos).contains(&e.pos) && !e.status.contains("petrified")) {
                    for weapon in 0..self.rules.units[&u.unit_type].weapons.len(){actions.push(Action::Attack{unit:u.id.clone(),target:e.id.clone(),weapon});}
                }
            }
        }
        for name in &self.sides[s-1].recruit {
            let t=&self.rules.units[name];
            if t.cost<=self.sides[s-1].gold {for p in self.castle_slots(s) {actions.push(Action::Recruit{unit_type:name.clone(),to:p});}}
        }
        Ok(actions)
    }
    pub fn step(&mut self,action:Action)->Result<Value,String>{
        if self.finished{return Err("game has ended".into());}
        let mut strikes=vec![];let mut interrupted=false;let mut actual=None;
        // Full moves share legality with ordinary moves, then consume remaining movement.
        let canonical=match &action {Action::Move{unit,to,..}=>Action::Move{unit:unit.clone(),to:*to,full:false},_=>action.clone()};
        if !self.legal_actions(self.current)?.contains(&canonical){return Err("action is absent from the player's legal intents".into());}
        match action.clone() {
            Action::EndTurn=>self.end_turn(),
            Action::Move{unit,to,full}=>{
                let i=self.unit(&unit).ok_or("unit missing")?;let u=self.units[i].clone();let (_,prev)=self.reach(&u,self.current);
                let mut path=vec![];let mut p=to;
                while p!=u.pos {path.push(p);p=prev[p];if p==usize::MAX{return Err("broken public path".into());}}
                path.reverse();
                let mut seen:BTreeSet<String>=self.public_units(self.current).iter().map(|u|u.id.clone()).collect();
                let hidden:BTreeSet<String>=self.units.iter().filter(|u|u.hp>0 && self.concealed(u,self.current)).map(|u|u.id.clone()).collect();
                let mut last_vacant=u.pos;
                for p in path {
                    if self.units.iter().any(|o|o.hp>0 && o.pos==p && self.enemy(self.current,o.side)){interrupted=true;break;}
                    let occupied=self.units.iter().enumerate().any(|(j,o)|j!=i && o.hp>0 && o.pos==p);
                    let t=&self.rules.units[&self.units[i].unit_type];
                    let teleport=!self.adjacent(self.units[i].pos).contains(&p);
                    let mut cost=if teleport{1}else{t.movement[&self.spec.terrain[p]].max(1)};
                    if self.units[i].status.contains("slowed"){cost=cost.saturating_mul(2);}
                    if cost>self.units[i].moves {interrupted=true;break;}
                    self.units[i].moves-=cost;self.units[i].pos=p;self.units[i].acted=true;
                    if !occupied {last_vacant=p;}
                    // Friendly units may be crossed, but their hex is neither a
                    // capture location nor a resting place after interruption.
                    if !occupied && self.rules.terrains[&self.spec.terrain[p]].village && self.village_owner[p]!=self.current {
                        self.village_owner[p]=self.current;self.units[i].moves=0;
                    }
                    self.update_visibility();
                    let visible=self.public_units(self.current);
                    let skirmisher=self.skirmisher_at(&self.units[i],p,&visible);
                    let contact=visible.iter().any(|e|self.enemy(self.current,e.side) && !seen.contains(&e.id));
                    let ambushed=visible.iter().any(|e|self.enemy(self.current,e.side) && !seen.contains(&e.id) && hidden.contains(&e.id));
                    let zoc=visible.iter().any(|e|self.enemy(self.current,e.side) && self.rules.units[&e.unit_type].level>0 && self.adjacent(p).contains(&e.pos) && !e.status.contains("petrified") && !e.status.contains("stunned"));
                    seen.extend(visible.into_iter().map(|u|u.id));
                    if ambushed || zoc && !skirmisher {self.units[i].moves=0;}
                    if p!=to && (contact || self.units[i].moves==0){interrupted=true;break;}
                }
                if self.units.iter().enumerate().any(|(j,o)|j!=i && o.hp>0 && o.pos==self.units[i].pos) {
                    self.units[i].pos=last_vacant;interrupted=true;
                }
                if full {self.units[i].moves=0;}actual=Some(self.units[i].pos);
            },
            Action::Recruit{unit_type,to}=>{
                // A hidden occupant can interrupt a public legal recruit. Reveal by
                // ordinary vision refresh, never overwrite the true occupying unit.
                if self.units.iter().any(|u|u.hp>0 && u.pos==to){interrupted=true;}
                else {
                    let t=&self.rules.units[&unit_type];self.sides[self.current-1].gold-=t.cost;
                    let mut id=format!("lite-{}",self.next_id);self.next_id+=1;
                    while self.unit(&id).is_some(){id=format!("lite-{}",self.next_id);self.next_id+=1;}
                    self.units.push(Unit{id,unit_type,side:self.current,pos:to,hp:t.hp,moves:0,attacks_left:0,
                        xp:0,leader:false,status:BTreeSet::new(),traits:BTreeSet::new(),acted:true,feeding_bonus:0,
                        resolved_max_hp:None,resolved_max_moves:None,resolved_max_experience:None,resolved_weapon_damage:vec![]});actual=Some(to);
                }
            },
            Action::Attack{unit,target,weapon}=>{
                let ai=self.unit(&unit).ok_or("attacker missing")?;let di=self.unit(&target).ok_or("defender missing")?;
                let mut a=self.units[ai].clone();let mut d=self.units[di].clone();
                let apos=a.pos;let dpos=d.pos;
                let modifiers=self.combat_modifiers(&a,&d,&self.units);
                let attacking=self.rules.units[&a.unit_type].weapons[weapon].clone();
                let counter=combat::counter_weapon(&self.rules,&d,&attacking).map(|i|self.rules.units[&d.unit_type].weapons[i].clone());
                strikes=combat::resolve(&self.rules,&mut a,&mut d,weapon,
                    &self.spec.terrain[apos],&self.spec.terrain[dpos],self.turn,&modifiers);
                // This is the standard core feeding death rule, not a WML event
                // interpreter. Its permanent object bonus survives advancement.
                let feed=|killer:&mut Unit,victim:&Unit|{
                    if killer.hp>0 && victim.hp<=0 && self.rules.units[&killer.unit_type].abilities.contains("feeding") &&
                        !self.rules.units[&victim.unit_type].abilities.contains("unplagueable") && !victim.status.contains("unplagueable") {
                        killer.feeding_bonus+=1;killer.hp+=1;
                    }
                };
                if d.hp<=0{feed(&mut a,&d);}else if a.hp<=0{feed(&mut d,&a);}
                let plague=if d.hp<=0{attacking.plague_type.clone().map(|name|(name,a.side,d.pos,d.unit_type.clone()))}
                    else if a.hp<=0{counter.and_then(|w|w.plague_type).map(|name|(name,d.side,a.pos,a.unit_type.clone()))}else{None};
                if let Some((name,side,pos,victim))=plague {
                    if !self.rules.terrains[&self.spec.terrain[pos]].village && !self.rules.units[&victim].abilities.contains("unplagueable") {
                        let t=&self.rules.units[&name];let id=format!("lite-{}",self.next_id);self.next_id+=1;
                        self.units.push(Unit{id,unit_type:name,side,pos,hp:t.hp,moves:0,attacks_left:0,
                            xp:0,leader:false,status:BTreeSet::new(),traits:BTreeSet::new(),acted:true,feeding_bonus:0,
                            resolved_max_hp:None,resolved_max_moves:None,resolved_max_experience:None,resolved_weapon_damage:vec![]});
                    }
                }
                self.units[ai]=a;self.units[di]=d;self.advance(ai);self.advance(di);
            }
        }
        self.revision+=1;self.check_victory();self.update_visibility();self.update_exploration(false);
        Ok(json!({"intent":action,"actual_pos":actual,"interrupted":interrupted,"strikes":strikes,
            "turn":self.turn,"current_side":self.current,"finished":self.finished,"truncated":self.truncated,"winner":self.winner}))
    }
    fn advance(&mut self,i:usize) {
        let u=&mut self.units[i];if u.hp<=0{return;}
        let t=&self.rules.units[&u.unit_type];
        let required=u.max_xp(&self.rules);
        if u.xp>=required {if let Some(next)=t.advances_to.first() {
            let nt=&self.rules.units[next];u.xp-=required;u.unit_type=next.clone();u.hp=nt.hp+u.feeding_bonus;
            u.resolved_max_hp=None;u.resolved_max_moves=None;u.resolved_max_experience=None;u.resolved_weapon_damage.clear();
            u.status.remove("poisoned");u.status.remove("slowed");
        }}
    }
    fn check_victory(&mut self) {
        for s in &mut self.sides {
            s.eliminated=!self.units.iter().any(|u|u.hp>0 && u.side==s.id && u.leader);
        }
        // Leaderless factions leave the board; public team identity stays in spec.
        let eliminated:BTreeSet<usize>=self.sides.iter().filter(|s|s.eliminated).map(|s|s.id).collect();
        for u in &mut self.units {if eliminated.contains(&u.side){u.hp=0;}}
        let teams:BTreeSet<String>=self.sides.iter().filter(|s|!s.eliminated).map(|s|s.team.clone()).collect();
        if teams.len()<=1{self.finished=true;self.winner=teams.into_iter().next();}
    }
    pub(crate) fn end_turn(&mut self) {
        let old=self.current;
        for u in self.units.iter_mut().filter(|u|u.hp>0 && u.side==old){u.status.remove("slowed");}
        for _ in 0..self.sides.len(){
            self.current=self.current%self.sides.len()+1;
            if self.current==1{self.turn+=1;}
            if !self.sides[self.current-1].eliminated {break;}
        }
        if self.turn>self.spec.max_turns{self.finished=true;self.truncated=true;return;}
        let s=self.current;let villages=self.village_owner.iter().filter(|&&v|v==s).count() as i32;
        let upkeep:i32=self.units.iter().filter(|u|u.hp>0 && u.side==s && !u.leader && !u.traits.contains("loyal"))
            .map(|u|self.rules.units[&u.unit_type].level as i32).sum();
        self.sides[s-1].gold+=self.sides[s-1].base_income+2*villages-(upkeep-villages).max(0);
        let healers:Vec<(usize,usize,i32,u8,Option<String>,bool)>=self.units.iter().filter(|u|u.hp>0 && !u.status.contains("petrified"))
            .filter_map(|u|{
                let t=&self.rules.units[&u.unit_type];
                let amount=t.healing_amount.unwrap_or(if t.abilities.contains("heals") || t.abilities.contains("healing"){4}else{0});
                let poison=match t.healing_poison.as_deref(){Some("cured")=>2,Some("slowed")=>1,
                    Some(_)=>0,None=>if t.abilities.contains("curing"){2}else if amount>0{1}else{0}};
                if amount>0 || poison>0{Some((u.side,u.pos,amount,poison,t.healing_excluded_status.clone(),t.curing_unfiltered))}else{None}
            }).collect();
        let width=self.spec.width;let height=self.spec.height;let team=self.sides[s-1].team.clone();
        for u in self.units.iter_mut().filter(|u|u.hp>0) {
            let t=&self.rules.units[&u.unit_type];let tile=&self.rules.terrains[&self.spec.terrain[u.pos]];
            if !u.status.contains("petrified") && !u.status.contains("unhealable") && self.sides[u.side-1].team==team {
                let own_turn=u.side==s;
                let terrain_heal=if own_turn{tile.healing.max(if tile.village{8}else{0})}else{0};
                let regenerates=own_turn && t.regeneration_terrains.as_ref().is_none_or(|terrains|terrains.contains(&self.spec.terrain[u.pos]));
                let regen=if regenerates{t.regeneration_amount.unwrap_or(if t.abilities.contains("regenerates") || t.abilities.contains("regeneration"){8}else{0})}else{0};
                let local_heal=terrain_heal.max(regen);
                let adjacent=neighbors(u.pos,width,height);
                let mut healing=local_heal;
                let regen_poison=if regenerates {match t.regeneration_poison.as_deref(){Some("cured")=>2,Some("slowed")=>1,Some(_)=>0,None=>if regen>0{2}else{0}}}else{0};
                let mut poison=if terrain_heal>0{2}else{regen_poison};
                for (side,pos,amount,treatment,excluded,curing_unfiltered) in &healers {
                    let (side,pos)=(*side,*pos);
                    if self.sides[side-1].team!=team || !adjacent.contains(&pos){continue;}
                    let excluded=excluded.as_ref().is_some_and(|status|u.status.contains(status));
                    let amount=if excluded{0}else{*amount};
                    let treatment=if excluded{if *curing_unfiltered{2}else{0}}else{*treatment};
                    if side==s {healing=healing.max(amount);poison=poison.max(treatment);}
                    else if own_turn {poison=poison.max(treatment.min(1));}
                }
                let rest=if own_turn && (!u.acted || u.traits.contains("healthy")){2}else{0};
                let change=if u.status.contains("poisoned") {
                    if poison==2 {u.status.remove("poisoned");}
                    rest-if own_turn && poison==0{POISON_TICK}else{0}
                }else{rest+healing};
                u.hp=(u.hp+change).clamp(1,u.max_hp(&self.rules));
            }
            if u.side==s {u.status.remove("stunned");u.moves=u.max_moves(&self.rules);u.attacks_left=1;u.acted=false;}
        }
    }
    fn public_income(&self,s:usize)->i32 {
        // Native `side.total_income` is gross income (base + owned village
        // gold); upkeep is a separate expense. Expose only villages the side
        // has observed so hidden ownership cannot leak through income.
        let villages=self.knowledge[s-1].villages.values().filter(|v|v.0==s).count() as i32;
        self.sides[s-1].base_income+2*villages
    }
    fn exploration_scope(&self,s:usize)->String {
        let side=&self.sides[s-1];
        let members:Vec<String>=self.sides.iter().filter(|other|other.id==s || other.team==side.team &&
            (side.share_view && other.share_view || side.share_maps && other.share_maps)).map(|other|other.id.to_string()).collect();
        members.join(":")
    }
    fn update_exploration(&mut self,initial:bool) {
        for s in 1..=self.sides.len() {
            let scope=self.exploration_scope(s);
            let visible:Vec<usize>=self.knowledge[s-1].visible.iter().enumerate().filter(|(_,v)|**v).map(|(p,_)|p).collect();
            let seen=self.exploration_seen.entry(scope.clone()).or_default();let mut new=0;
            for p in visible {if seen.insert(p){new+=1;}}
            let earned=self.exploration_earned.entry(scope).or_insert(0.);
            if !initial && self.sides[s-1].fog {*earned=(*earned+new as f64/self.spec.terrain.len() as f64).min(1.);}
        }
    }
    /// Judge-only scalars. No unit, tile, ownership or opponent-gold DTO escapes.
    pub fn reward_labels(&self,s:usize)->Value {
        let mut amounts:BTreeMap<String,(f64,usize)>=BTreeMap::new();
        for side in &self.sides {
            let army:f64=self.units.iter().filter(|u|u.hp>0 && u.side==side.id).map(|u|{
                let t=&self.rules.units[&u.unit_type];t.cost as f64*u.hp as f64/u.max_hp(&self.rules) as f64
            }).sum();
            let villages=self.village_owner.iter().filter(|&&v|v==side.id).count();
            let entry=amounts.entry(side.team.clone()).or_insert((0.,0));entry.0+=side.gold as f64+army+20.*villages as f64;entry.1+=1;
        }
        let own=&self.sides[s-1].team;let mut total=200.;let mut others=0.;let mut n=0.;let mut mine=0.;
        for (team,(amount,count)) in amounts {let mean=amount/count as f64;total+=mean.abs();if &team==own{mine=mean;}else{others+=mean;n+=1.;}}
        let mut weight:f64=0.;
        for (p,code) in self.spec.terrain.iter().enumerate(){let x=p%self.spec.width+1;let y=p/self.spec.width+1;
            let t=&self.rules.terrains[code];weight+=if t.village{4.}else if t.keep{2.}else if code.starts_with('R') || x%4==1 && y%4==1{1.}else{0.};}
        json!({"economy":if n>0.{(mine-others/n)/total}else{0.},
            "explored":if self.sides[s-1].fog{*self.exploration_earned.get(&self.exploration_scope(s)).unwrap_or(&0.)}else{0.},
            "total_strategic_weight":weight.max(1.)})
    }
    /// `expected_damage_v1` forecast: one deterministic resolution from the
    /// requesting side's public context. `samples` stays accepted for compatibility
    /// with existing callers and is ignored, because there is nothing to sample.
    pub fn forecast(&self,s:usize,attacker:&str,target:&str,weapon:usize,_samples:usize)->Result<Value,String>{
        self.side_check(s)?;
        let public=self.public_units(s);
        let a=public.iter().find(|u|u.id==attacker).ok_or("attacker not visible")?;
        let d=public.iter().find(|u|u.id==target).ok_or("target not visible")?;
        if weapon>=self.rules.units[&a.unit_type].weapons.len(){return Err("invalid weapon".into());}
        let at=self.knowledge[s-1].terrain[a.pos].as_ref().ok_or("unknown attacker terrain")?;
        let dt=self.knowledge[s-1].terrain[d.pos].as_ref().ok_or("unknown defender terrain")?;
        let modifiers=self.combat_modifiers(a,d,&public);
        let mut aa=a.clone();let mut dd=d.clone();
        combat::resolve(&self.rules,&mut aa,&mut dd,weapon,at,dt,self.turn,&modifiers);
        let side=|u:&Unit|{
            let hp=u.hp.max(0);
            json!({"average_hp":hp,"hp_chance":BTreeMap::from([(hp.to_string(),1.0)]),
                "poisoned":i32::from(u.status.contains("poisoned")),"slowed":i32::from(u.status.contains("slowed"))})
        };
        Ok(json!({"approximate":false,"samples":1,"combat_version":COMBAT_VERSION,
            "attacker":side(&aa),"defender":side(&dd)}))
    }
    fn combat_modifiers(&self,a:&Unit,d:&Unit,context:&[Unit])->combat::Modifiers {
        let leadership=|target:&Unit|{
            let adjacent=self.adjacent(target.pos);
            let vanguard=if self.rules.units[&target.unit_type].abilities.contains("vanguard") {
                25*(context.iter().filter(|u|u.hp>0 && adjacent.contains(&u.pos)).count().saturating_sub(1).min(5)) as i32
            }else{0};
            context.iter().filter(|u|u.hp>0 && !u.status.contains("petrified") && !self.enemy(u.side,target.side) &&
            self.adjacent(target.pos).contains(&u.pos)).map(|u|{
                let source=&self.rules.units[&u.unit_type];let level=self.rules.units[&target.unit_type].level;
                if source.abilities.contains("inspire") && source.level>=level{25*(source.level-level+1) as i32}
                else if source.abilities.contains("leadership"){25*source.level.saturating_sub(level) as i32}else{0}
            }).max().unwrap_or(0)+vanguard
        };
        let initiative=|target:&Unit|context.iter().any(|u|u.hp>0 && !u.status.contains("petrified") &&
            !self.enemy(u.side,target.side) && self.adjacent(target.pos).contains(&u.pos) &&
            self.rules.units[&u.unit_type].abilities.contains("initiative"));
        let mut light=0;let mut dark=0;
        for u in context.iter().filter(|u|u.hp>0 && !u.status.contains("petrified") &&
            (u.pos==a.pos || u.pos==d.pos || self.adjacent(a.pos).contains(&u.pos) || self.adjacent(d.pos).contains(&u.pos))) {
            let t=&self.rules.units[&u.unit_type];let value=t.illumination.unwrap_or(if t.abilities.contains("illuminates"){25}else{0});
            light=light.max(value);dark=dark.min(value);
        }
        let diversion=|target:&Unit|context.iter().filter(|source|source.hp>0 && !source.status.contains("petrified") &&
            self.enemy(source.side,target.side) && self.adjacent(target.pos).contains(&source.pos) &&
            self.rules.units[&source.unit_type].abilities.contains("diversion")).filter(|source|{
                let tq=(target.pos%self.spec.width) as i32;let tr=(target.pos/self.spec.width) as i32-tq/2;
                let sq=(source.pos%self.spec.width) as i32;let sr=(source.pos/self.spec.width) as i32-sq/2;
                let q=2*tq-sq;let y=2*tr-sr+q.div_euclid(2);
                q>=0 && q<self.spec.width as i32 && y>=0 && y<self.spec.height as i32 && context.iter().any(|other|
                    other.hp>0 && !other.status.contains("petrified") && other.pos==y as usize*self.spec.width+q as usize && self.enemy(other.side,target.side))
            }).count() as u32*20;
        let aq=(a.pos%self.spec.width) as i32;let ar=(a.pos/self.spec.width) as i32-aq/2;
        let dq=(d.pos%self.spec.width) as i32;let dr=(d.pos/self.spec.width) as i32-dq/2;
        let oq=2*dq-aq;let oy=2*dr-ar+oq.div_euclid(2);
        let behind=if oq>=0 && oq<self.spec.width as i32 && oy>=0 && oy<self.spec.height as i32 {Some(oy as usize*self.spec.width+oq as usize)}else{None};
        let backstab=behind.is_some_and(|p|context.iter().any(|u|u.hp>0 && u.pos==p && !self.enemy(u.side,a.side) && !u.status.contains("petrified")));
        combat::Modifiers{attacker_leadership:leadership(a),defender_leadership:leadership(d),illumination:light+dark,backstab,
            attacker_cth_sub:diversion(a),defender_cth_sub:diversion(d),
            attacker_firststrike:initiative(a),defender_firststrike:initiative(d)}
    }
}
