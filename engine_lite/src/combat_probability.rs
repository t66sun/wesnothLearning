//! Native-compatible finite combat distributions. Merge equal HP/status states after each blow;
//! no sampling, hidden state, RNG reads, or probability pruning. Native berserk
//! prediction stops once death probability reaches 99%; execution does not.
//! Native advancement healing and poison marginals are prediction approximations.
use crate::{combat::{self,Modifiers},model::{Rules,Unit,Weapon}};
use std::collections::BTreeMap;
use serde_json::{json,Value};

#[derive(Clone,Copy,PartialEq,Eq,PartialOrd,Ord)]
struct State { ah:i32,dh:i32,as_:u8,ds:u8,an:u32,dn:u32 }
const FLAGS:[&str;4]=["poisoned","slowed","petrified","stunned"];
fn flags(u:&Unit)->u8 {FLAGS.iter().enumerate().fold(0,|v,(i,s)|v|if u.status.contains(*s){1<<i}else{0})}
fn restore(u:&Unit,hp:i32,status:u8)->Unit {
    let mut u=u.clone();u.hp=hp;
    for (i,s) in FLAGS.iter().enumerate() {if status&(1<<i)!=0 {u.status.insert((*s).into());}else{u.status.remove(*s);}}
    u
}
impl State {
    fn new(a:&Unit,d:&Unit)->Self {Self{ah:a.hp,dh:d.hp,as_:flags(a),ds:flags(d),an:0,dn:0}}
    fn done(self)->bool {self.ah<=0 || self.dh<=0 || (self.as_|self.ds)&4!=0}
}
pub struct Distribution { states:BTreeMap<State,f64>, poisoned:[f64;2], approximate:bool }
impl Distribution {
    pub fn json(&self)->Value {
        let side=|defense:bool| {
            let mut hp=BTreeMap::<String,f64>::new();let mut mean=0.;let mut slow=0.;
            for (s,p) in &self.states {
                let (h,status)=if defense{(s.dh,s.ds)}else{(s.ah,s.as_)};
                *hp.entry(h.max(0).to_string()).or_default()+=p;mean+=f64::from(h.max(0))*p;
                if status&2!=0 {slow+=p;}
            }
            json!({"average_hp":mean,"hp_chance":hp,"poisoned":self.poisoned[usize::from(defense)],"slowed":slow})
        };
        json!({"attacker":side(false),"defender":side(true),"approximate":self.approximate,
            "samples":0,"combat_version":crate::model::COMBAT_VERSION})
    }
    fn score(&self)->[f64;3] {
        let mut hp=[0.;2];let mut dead=[0.;2];
        for (s,p) in &self.states {
            for (i,h) in [s.ah,s.dh].into_iter().enumerate() {
                hp[i]+=f64::from(h.max(0))*p;if h<=0 {dead[i]+=p;}
            }
        }
        // Native's poisoned marginal includes fatal hits; its defense score
        // subtracts death probability before charging the surviving poison cost.
        let poison=|i:usize|if self.poisoned[i]>0. {
            (self.poisoned[i]-dead[i])*f64::from(crate::state::POISON_TICK)
        }else{0.};
        [dead[0]-dead[1],hp[1]-poison(1)-hp[0]+poison(0),-hp[0]]
    }
}
fn better(a:&Distribution,b:&Distribution)->bool {
    let aa=a.score();let bb=b.score();
    for i in 0..2 {if (aa[i]-bb[i]).abs()>0.01{return aa[i]>bb[i];}}
    aa[2]>bb[2]
}
fn count(u:&Unit,w:&Weapon,r:&Rules)->u32 {
    if w.specials.contains("swarm"){((i64::from(w.strikes)*i64::from(u.hp))/i64::from(u.max_hp(r))).max(1) as u32}else{w.strikes}
}
fn distribution(r:&Rules,a:&Unit,d:&Unit,aw:&Weapon,counter:Option<usize>,at:&str,dt:&str,turn:u32,m:&Modifiers)->Distribution {
    let dw=counter.map(|i|combat::resolved_weapon(r,d,i));
    let charge=aw.specials.contains("charge");
    let rounds=if aw.specials.contains("berserk") || dw.as_ref().is_some_and(|w|w.specials.contains("berserk")){30}else{1};
    let af=aw.specials.contains("firststrike") || (m.attacker_firststrike && dw.as_ref().is_some_and(|w|w.range=="melee"));
    let df=dw.as_ref().is_some_and(|w|w.specials.contains("firststrike") || (m.defender_firststrike && aw.range=="melee"));
    let mut states=BTreeMap::from([(State::new(a,d),1.)]);
    let mut approximate=false;
    for round in 0..rounds {
        let mut initialized=BTreeMap::new();let mut max_count=0;
        for (mut s,p) in states {
            if !s.done() {
                s.an=count(&restore(a,s.ah,s.as_),aw,r);
                s.dn=dw.as_ref().map_or(0,|w|count(&restore(d,s.dh,s.ds),w,r));
                if let Some(limit)=aw.opponent_attacks{s.dn=s.dn.min(limit);}
                max_count=max_count.max(s.an.max(s.dn));
            }
            *initialized.entry(s).or_insert(0.)+=p;
        }
        states=initialized;
        for n in 0..max_count {
            for defense in if df && !af{[true,false]}else{[false,true]} {
                let mut next=BTreeMap::new();
                for (s,p) in states {
                    if s.done() || n>=if defense{s.dn}else{s.an} {
                        *next.entry(s).or_insert(0.)+=p;continue;
                    }
                    let mut aa=restore(a,s.ah,s.as_);let mut dd=restore(d,s.dh,s.ds);
                    let hit=if defense {
                        combat::strike(r,&mut dd,&mut aa,dw.as_ref().unwrap(),Some(aw),at,turn,charge,false,m,0)
                    }else{combat::strike(r,&mut aa,&mut dd,aw,dw.as_ref(),dt,turn,charge,true,m,0)};
                    let chance=f64::from(hit.chance)/100.;
                    if chance<1. {*next.entry(s).or_insert(0.)+=p*(1.-chance);}
                    if chance>0. {
                        let mut success=State::new(&aa,&dd);success.an=s.an;success.dn=s.dn;
                        // The native prediction counts debuffs on fatal blows too,
                        // although execution only applies statuses to survivors.
                        let (target,weapon,status)=if defense{(a,dw.as_ref().unwrap(),&mut success.as_)}else{(d,aw,&mut success.ds)};
                        if weapon.specials.contains("poison") && !r.units[&target.unit_type].abilities.contains("unpoisonable") && !target.status.contains("unpoisonable") {*status|=1;}
                        if weapon.specials.contains("slow") {*status|=2;}
                        *next.entry(success).or_insert(0.)+=p*chance;
                    }
                } states=next;
            }
        }
        if states.keys().all(|s|s.done()){break;}
        // Wesnoth 1.18.8 attack_prediction.cpp uses the same 0.99 stopping rule.
        let dead:f64=states.iter().filter(|(s,_)|s.ah<=0 || s.dh<=0).map(|(_,p)|p).sum();
        if round+1<rounds && dead>=0.99 {approximate=true;break;}
    }
    let units=[a,d];
    let levels=[r.units[&a.unit_type].level,r.units[&d.unit_type].level];
    let forced=[a.xp.saturating_add(levels[1])>=a.max_xp(r),d.xp.saturating_add(levels[0])>=d.max_xp(r)];
    let heals=[a.xp.saturating_add(combat::kill_xp(levels[1]))>=a.max_xp(r),d.xp.saturating_add(combat::kill_xp(levels[0]))>=d.max_xp(r)];
    let mut dead=[0.;2];let mut poisoned=[0.;2];
    for (s,p) in &states {
        for (i,(hp,status)) in [(s.ah,s.as_),(s.dh,s.ds)].into_iter().enumerate() {
            if hp<=0 {dead[i]+=p;}if status&1!=0 {poisoned[i]+=p;}
        }
    }
    for i in 0..2 {
        if forced[i] {poisoned[i]=0.;}
        else if heals[i] {
            // Match native calculate_probability_of_debuff: conditional poison
            // recovery is estimated from touched, survival and kill marginals.
            let alive=(1.-dead[i]).max(0.);let kill=dead[1-i].clamp(0.,1.);
            if units[i].status.contains("poisoned") {poisoned[i]=1.-kill;}
            else if alive>0. && poisoned[i]>0. {poisoned[i]-=(alive-1.+poisoned[i])*kill/alive;}
        }
    }
    if !heals.iter().any(|&h|h) {return Distribution{states,poisoned,approximate};}
    // Native predicts healing to the current max HP, not an advancement choice.
    let approximate=approximate || (0..2).any(|i| (forced[i] && dead[i]<1.) || (heals[i] && dead[1-i]>0.));
    let mut healed=BTreeMap::new();
    for (mut s,p) in states {
        let killed=[s.dh<=0,s.ah<=0];
        for (i,(hp,status)) in [(&mut s.ah,&mut s.as_),(&mut s.dh,&mut s.ds)].into_iter().enumerate() {
            if *hp>0 && (forced[i] || heals[i] && killed[i]) {
                *hp=units[i].max_hp(r);*status &= !3;
            }
            if forced[i] {*status &= !2;}
        }
        *healed.entry(s).or_insert(0.)+=p;
    }
    Distribution{states:healed,poisoned,approximate}
}

pub fn select(r:&Rules,a:&Unit,d:&Unit,weapon:usize,at:&str,dt:&str,turn:u32,m:&Modifiers)->(Option<usize>,Distribution) {
    let aw=combat::resolved_weapon(r,a,weapon);
    let mut choices=r.units[&d.unit_type].weapons.iter().enumerate().filter(|(_,w)|w.range==aw.range && w.defense_weight>0.).map(|(i,_)|i);
    let mut best=choices.next();
    let mut result=distribution(r,a,d,&aw,best,at,dt,turn,m);
    for counter in choices {
        let candidate=distribution(r,a,d,&aw,Some(counter),at,dt,turn,m);
        if better(&candidate,&result){best=Some(counter);result=candidate;}
    }
    (best,result)
}
