//! Exact finite combat distributions. Merge equal HP/status states after each blow;
//! no sampling, hidden state, RNG reads, or probability pruning in forecasts.
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
pub struct Distribution { states:BTreeMap<State,f64> }
impl Distribution {
    pub fn json(&self)->Value {
        let side=|defense:bool| {
            let mut hp=BTreeMap::<String,f64>::new();let mut mean=0.;let mut poison=0.;let mut slow=0.;
            for (s,p) in &self.states {
                let (h,status)=if defense{(s.dh,s.ds)}else{(s.ah,s.as_)};
                *hp.entry(h.max(0).to_string()).or_default()+=p;mean+=f64::from(h.max(0))*p;
                if status&1!=0 {poison+=p;} if status&2!=0 {slow+=p;}
            }
            json!({"average_hp":mean,"hp_chance":hp,"poisoned":poison,"slowed":slow})
        };
        json!({"attacker":side(false),"defender":side(true),"approximate":false,
            "samples":0,"combat_version":crate::model::COMBAT_VERSION})
    }
    fn score(&self)->[f64;3] {
        let mut v=[0.;3];
        for (s,p) in &self.states {
            let hp=|h:i32,f:u8|f64::from(h.max(0)-if h>0 && f&1!=0{crate::state::POISON_TICK}else{0});
            v[0]+=(i32::from(s.ah<=0)-i32::from(s.dh<=0)) as f64*p;
            v[1]+=(hp(s.dh,s.ds)-hp(s.ah,s.as_))*p;
            v[2]-=f64::from(s.ah.max(0))*p;
        } v
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
    for _ in 0..rounds {
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
                        *next.entry(success).or_insert(0.)+=p*chance;
                    }
                } states=next;
            }
        }
        if states.keys().all(|s|s.done()){break;}
    }
    Distribution{states}
}

pub fn select(r:&Rules,a:&Unit,d:&Unit,weapon:usize,at:&str,dt:&str,turn:u32,m:&Modifiers)->(Option<usize>,Distribution) {
    let aw=combat::resolved_weapon(r,a,weapon);
    let mut choices=r.units[&d.unit_type].weapons.iter().enumerate().filter(|(_,w)|w.range==aw.range).map(|(i,_)|i);
    let mut best=choices.next();
    let mut result=distribution(r,a,d,&aw,best,at,dt,turn,m);
    for counter in choices {
        let candidate=distribution(r,a,d,&aw,Some(counter),at,dt,turn,m);
        if better(&candidate,&result){best=Some(counter);result=candidate;}
    }
    (best,result)
}
