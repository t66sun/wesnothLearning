use crate::model::{Random, Rules, Unit, Weapon};
use serde::{Deserialize,Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Strike {
    pub attacker: String,
    pub defender: String,
    pub hit: bool,
    pub chance: u32,
    pub damage: i32,
    pub defender_hp: i32,
}
#[derive(Default)]
pub struct Modifiers {
    pub attacker_leadership:i32,
    pub defender_leadership:i32,
    pub illumination:i32,
    pub backstab:bool,
    pub attacker_cth_sub:u32,
    pub defender_cth_sub:u32,
    pub attacker_firststrike:bool,
    pub defender_firststrike:bool,
}
pub fn counter_weapon(rules:&Rules,defender:&Unit,attack:&Weapon)->Option<usize> {
    rules.units[&defender.unit_type].weapons.iter().enumerate()
        .filter(|(_,w)|w.range==attack.range)
        .max_by_key(|(_,w)|w.damage*w.strikes as i32).map(|(i,_)|i)
}
fn strike(rules:&Rules,rng:&mut Random,a:&mut Unit,d:&mut Unit,w:&Weapon,
          opposing_weapon:Option<&Weapon>,terrain:&str,turn:u32,charging:bool,
          offense:bool,modifiers:&Modifiers)->Strike {
    let at=&rules.units[&a.unit_type];let dt=&rules.units[&d.unit_type];
    let mut chance=dt.defense[terrain];
    if w.specials.contains("magical") { chance=70; }
    if offense && w.specials.contains("marksman") { chance=chance.max(60); }
    chance=chance.saturating_sub(if offense{modifiers.attacker_cth_sub}else{modifiers.defender_cth_sub});
    if offense { chance=chance.saturating_sub(opposing_weapon.map_or(0,|other|other.defense_cth_sub)); }
    let lawful=(rules.lawful_bonus[(turn as usize-1)%rules.lawful_bonus.len()]+modifiers.illumination).clamp(-25,25);
    let tod=match at.alignment.as_str() { "lawful"=>lawful,"chaotic"=>-lawful,"liminal"=>-lawful.abs(),_=>0 };
    let mut resist=*dt.resistance.get(&w.damage_type).unwrap_or(&100);
    if offense && dt.abilities.contains("steadfast") && resist<100 {resist=(100-2*(100-resist)).max(50);}
    let leadership=if offense{modifiers.attacker_leadership}else{modifiers.defender_leadership};
    let mut numerator=w.damage*(100+tod+leadership)*resist;
    if a.status.contains("slowed") { numerator=(numerator+1)/2; }
    if charging { numerator*=2; }
    if offense && modifiers.backstab && w.specials.contains("backstab") {numerator*=2;}
    // Wesnoth's exact compound-modifier rounding remains an explicit approximation.
    // Absorb belongs to the selected opposing weapon and works in either role.
    // Keep it in the compound damage calculation, before the single rounding.
    let percent=opposing_weapon.and_then(|other|other.opponent_damage_percent).unwrap_or(100);
    let mut damage=((i64::from(numerator)*i64::from(percent)+500000)/1000000)
        .max(if w.damage>0 {1} else {0}) as i32;
    if w.specials.contains("swarm") { damage=damage.max(0); }
    let hit=rng.hit(chance);let dealt=if hit {damage.min(d.hp).max(0)} else {0};
    if hit {
        d.hp-=dealt;
        if w.specials.contains("drains") && !dt.abilities.contains("undrainable") {
            a.hp=(a.hp+(i64::from(dealt)*i64::from(w.drain_percent.unwrap_or(50))/100) as i32).min(a.max_hp(rules));
        }
        if d.hp>0 {
            if w.specials.contains("poison") && !dt.abilities.contains("unpoisonable") { d.status.insert("poisoned".into()); }
            if w.specials.contains("slow") { d.status.insert("slowed".into()); }
            if w.specials.contains("petrifies") { d.status.insert("petrified".into()); }
            if w.specials.contains("stun") { d.status.insert("stunned".into()); }
        }
    }
    Strike{attacker:a.id.clone(),defender:d.id.clone(),hit,chance,damage:dealt,defender_hp:d.hp}
}
pub fn resolve(rules:&Rules,rng:&mut Random,a:&mut Unit,d:&mut Unit,weapon:usize,
               attacker_terrain:&str,defender_terrain:&str,turn:u32,modifiers:&Modifiers)->Vec<Strike> {
    let mut aw=rules.units[&a.unit_type].weapons[weapon].clone();
    if let Some(&damage)=a.resolved_weapon_damage.get(weapon){aw.damage=damage;}
    let dw=counter_weapon(rules,d,&aw).map(|i|{let mut w=rules.units[&d.unit_type].weapons[i].clone();if let Some(&damage)=d.resolved_weapon_damage.get(i){w.damage=damage;}w});
    let charge=aw.specials.contains("charge");
    let berserk=aw.specials.contains("berserk") || dw.as_ref().is_some_and(|w|w.specials.contains("berserk"));
    let mut log=vec![];
    for _ in 0..if berserk {30} else {1} {
        let count=|u:&Unit,w:&Weapon|if w.specials.contains("swarm") {
            ((w.strikes as i32*u.hp)/u.max_hp(rules)).max(1) as u32
        } else {w.strikes};
        let an=count(a,&aw);let mut dn=dw.as_ref().map(|w|count(d,w)).unwrap_or(0);
        if let Some(limit)=aw.opponent_attacks {dn=dn.min(limit);}
        let attacker_first=aw.specials.contains("firststrike") ||
            (modifiers.attacker_firststrike && dw.as_ref().is_some_and(|w|w.range=="melee"));
        let defender_first=dw.as_ref().is_some_and(|w|w.specials.contains("firststrike") ||
            (modifiers.defender_firststrike && aw.range=="melee"));
        let first=defender_first && !attacker_first;
        for n in 0..an.max(dn) {
            for defense in if first {[true,false]} else {[false,true]} {
                if a.hp<=0 || d.hp<=0 || a.status.contains("petrified") || d.status.contains("petrified") { break; }
                if defense && n<dn { log.push(strike(rules,rng,d,a,dw.as_ref().unwrap(),Some(&aw),attacker_terrain,turn,charge,false,modifiers)); }
                if !defense && n<an { log.push(strike(rules,rng,a,d,&aw,dw.as_ref(),defender_terrain,turn,charge,true,modifiers)); }
            }
            if a.hp<=0 || d.hp<=0 || a.status.contains("petrified") || d.status.contains("petrified") { break; }
        }
        if a.hp<=0 || d.hp<=0 || a.status.contains("petrified") || d.status.contains("petrified") {break;}
    }
    let al=rules.units[&a.unit_type].level;let dl=rules.units[&d.unit_type].level;
    if a.hp>0 {a.xp+=if d.hp<=0 {8*dl.max(1)} else {dl};}
    if d.hp>0 {d.xp+=if a.hp<=0 {8*al.max(1)} else {al};}
    a.moves=0;a.attacks_left=a.attacks_left.saturating_sub(1);a.acted=true;
    log
}
