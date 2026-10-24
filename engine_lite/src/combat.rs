use crate::model::{Rules, Unit, Weapon};
use serde::{Deserialize,Serialize};

/// `expected_damage_v1`: every strike resolves its expected damage exactly, so a
/// battle has one deterministic outcome instead of a random sample. Hit chance is
/// still computed and reported; it scales the damage instead of deciding a roll.
pub const SLOW_DAMAGE_NUMERATOR: i64 = 3;
pub const SLOW_DAMAGE_DENOMINATOR: i64 = 4;
/// Ten percent uplift applied once, folded into the same integer rounding.
pub const DAMAGE_PERCENT: i64 = 110;
/// Percent uplift times percent chance: 110 * 100.
pub const DAMAGE_SCALE: i64 = 10_000;

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
/// Slowed strikes deal three quarters of the modified damage, rounded up.
pub fn slowed_damage(damage:i64)->i64 {
    (SLOW_DAMAGE_NUMERATOR*damage+SLOW_DAMAGE_DENOMINATOR-1)/SLOW_DAMAGE_DENOMINATOR
}
/// `ceil(damage*chance*1.10/100)` with wide integers and one final rounding.
pub fn expected_damage(damage:i64,chance:u32)->i64 {
    let percent=i64::from(chance.min(100));
    (damage*DAMAGE_PERCENT*percent+DAMAGE_SCALE-1)/DAMAGE_SCALE
}
fn strike(rules:&Rules,a:&mut Unit,d:&mut Unit,w:&Weapon,
          opposing_weapon:Option<&Weapon>,terrain:&str,turn:u32,charging:bool,
          offense:bool,modifiers:&Modifiers)->Strike {
    let at=&rules.units[&a.unit_type];let dt=&rules.units[&d.unit_type];
    let mut chance=dt.defense[terrain];
    if w.specials.contains("magical") { chance=70; }
    if offense && w.specials.contains("marksman") { chance=chance.max(60); }
    chance=chance.saturating_sub(if offense{modifiers.attacker_cth_sub}else{modifiers.defender_cth_sub});
    if offense { chance=chance.saturating_sub(opposing_weapon.map_or(0,|other|other.defense_cth_sub)); }
    let chance=chance.min(100);
    let lawful=(rules.lawful_bonus[(turn as usize-1)%rules.lawful_bonus.len()]+modifiers.illumination).clamp(-25,25);
    let tod=match at.alignment.as_str() { "lawful"=>lawful,"chaotic"=>-lawful,"liminal"=>-lawful.abs(),_=>0 };
    let mut resist=*dt.resistance.get(&w.damage_type).unwrap_or(&100);
    if offense && dt.abilities.contains("steadfast") && resist<100 {resist=(100-2*(100-resist)).max(50);}
    let leadership=if offense{modifiers.attacker_leadership}else{modifiers.defender_leadership};
    let mut numerator=w.damage*(100+tod+leadership)*resist;
    if charging { numerator*=2; }
    if offense && modifiers.backstab && w.specials.contains("backstab") {numerator*=2;}
    // Wesnoth's exact compound-modifier rounding remains an explicit approximation.
    // Absorb belongs to the selected opposing weapon and works in either role.
    // Keep it in the compound damage calculation, before the single rounding.
    let percent=opposing_weapon.and_then(|other|other.opponent_damage_percent).unwrap_or(100);
    let base=((i64::from(numerator)*i64::from(percent)+500000)/1000000)
        .max(if w.damage>0 {1} else {0});
    // The only slowed effect on damage is the three-quarter multiplier, applied to
    // the fully modified strike damage before the hit chance uplift.
    let modified=if a.status.contains("slowed") {slowed_damage(base)} else {base};
    let connected=chance>0;
    let dealt=(if connected {expected_damage(modified,chance).min(i64::from(d.hp)).max(0)} else {0}) as i32;
    if connected {
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
    Strike{attacker:a.id.clone(),defender:d.id.clone(),hit:chance>0,chance,damage:dealt,defender_hp:d.hp}
}
pub fn resolve(rules:&Rules,a:&mut Unit,d:&mut Unit,weapon:usize,
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
                if defense && n<dn { log.push(strike(rules,d,a,dw.as_ref().unwrap(),Some(&aw),attacker_terrain,turn,charge,false,modifiers)); }
                if !defense && n<an { log.push(strike(rules,a,d,&aw,dw.as_ref(),defender_terrain,turn,charge,true,modifiers)); }
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Rules, UnitType};
    use std::collections::{BTreeMap, BTreeSet};

    const PLAIN: &str = "Gg";

    fn weapon(damage: i32, strikes: u32, specials: &[&str]) -> Weapon {
        Weapon {
            id: "blade".into(), damage, strikes, damage_type: "blade".into(),
            range: "melee".into(),
            specials: specials.iter().map(|s| s.to_string()).collect(),
            plague_type: None, drain_percent: None, opponent_damage_percent: None,
            defense_cth_sub: 0, opponent_attacks: None,
        }
    }

    fn unit_type(id: &str, hp: i32, defense: u32, weapons: Vec<Weapon>) -> UnitType {
        UnitType {
            id: id.into(), scope: "test".into(), hp, moves: 5, vision: 5, level: 1,
            cost: 10, experience: 20, alignment: "neutral".into(), advances_to: vec![],
            weapons,
            movement: BTreeMap::from([(PLAIN.to_string(), 1)]),
            defense: BTreeMap::from([(PLAIN.to_string(), defense)]),
            resistance: BTreeMap::from([("blade".to_string(), 100)]),
            abilities: BTreeSet::new(), healing_amount: None, healing_poison: None,
            healing_excluded_status: None, curing_unfiltered: false,
            regeneration_amount: None, regeneration_poison: None,
            regeneration_terrains: None, illumination: None,
            concealment_terrains: BTreeSet::new(), concealment_requires_full_moves: false,
            unsupported: vec![], approximation_reasons: vec![],
        }
    }

    fn rules(defender_defense: u32, attacker: Vec<Weapon>, defender: Vec<Weapon>) -> Rules {
        let mut units = BTreeMap::new();
        units.insert("A".to_string(), unit_type("A", 40, defender_defense, attacker));
        units.insert("D".to_string(), unit_type("D", 40, defender_defense, defender));
        let mut terrains = BTreeMap::new();
        terrains.insert(PLAIN.to_string(), crate::model::Terrain {
            id: PLAIN.into(), village: false, castle: false, keep: false, healing: 0,
            concealment: BTreeSet::new(),
        });
        Rules {
            source_version: "1.18.8".into(), rules_version: "test".into(),
            source_hash: "test".into(), units, terrains, lawful_bonus: vec![0],
        }
    }

    fn unit(id: &str, unit_type: &str, hp: i32) -> Unit {
        Unit {
            id: id.into(), unit_type: unit_type.into(), side: if id == "a" { 1 } else { 2 },
            pos: if id == "a" { 0 } else { 1 }, hp, moves: 5, attacks_left: 1,
            xp: 0, leader: false, status: BTreeSet::new(), traits: BTreeSet::new(),
            acted: false, feeding_bonus: 0, resolved_max_hp: None,
            resolved_max_moves: None, resolved_max_experience: None,
            resolved_weapon_damage: vec![],
        }
    }

    fn strike_once(rules: &Rules, attacker: &mut Unit, defender: &mut Unit,
                   weapon_index: usize) -> Strike {
        resolve(rules, attacker, defender, weapon_index, PLAIN, PLAIN, 1, &Modifiers::default())
            .into_iter().next().expect("one strike")
    }

    #[test]
    fn expected_damage_matches_the_r1_table() {
        // D=10 at 60% defense: 10*60*1.10/100 = 6.6 -> 7.
        let rules_60 = rules(60, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let hit = strike_once(&rules_60, &mut a, &mut d, 0);
        assert_eq!((hit.chance, hit.damage, hit.hit), (60, 7, true));
        assert_eq!(d.hp, 33);
        // A second damage value catches a scale error that still rounds 10@60 to 7.
        let rules_13 = rules(60, vec![weapon(13, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        assert_eq!(strike_once(&rules_13, &mut a, &mut d, 0).damage, 9);
        // 100% chance: exactly the 10% uplift, 11.
        let rules_100 = rules(100, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        assert_eq!(strike_once(&rules_100, &mut a, &mut d, 0).damage, 11);
        // 1% chance rounds up to one point instead of vanishing.
        let rules_1 = rules(1, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        assert_eq!(strike_once(&rules_1, &mut a, &mut d, 0).damage, 1);
    }

    #[test]
    fn slowed_damage_is_three_quarters_rounded_up_then_scaled() {
        // Slowed D=10 -> S=8, then 8*60*1.10/100 = 5.28 -> 6.
        let rules = rules(60, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        a.status.insert("slowed".into());
        let hit = strike_once(&rules, &mut a, &mut d, 0);
        assert_eq!((hit.damage, d.hp), (6, 34));
        assert_eq!(slowed_damage(10), 8);
        assert_eq!(slowed_damage(11), 9);
    }

    #[test]
    fn zero_chance_never_connects_or_applies_status() {
        let rules = rules(0, vec![weapon(10, 1, &["poison", "slow"])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let hit = strike_once(&rules, &mut a, &mut d, 0);
        assert_eq!((hit.chance, hit.hit, hit.damage), (0, false, 0));
        assert!(d.status.is_empty());
        assert_eq!(d.hp, 40);
    }

    #[test]
    fn zero_damage_strike_connects_and_applies_status() {
        let rules = rules(100, vec![weapon(0, 1, &["poison", "slow"])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let hit = strike_once(&rules, &mut a, &mut d, 0);
        assert_eq!((hit.damage, hit.hit), (0, true));
        assert_eq!(d.status, BTreeSet::from(["poisoned".to_string(), "slowed".to_string()]));
    }

    #[test]
    fn resolve_keeps_strike_order_and_retaliation() {
        let rules = rules(60, vec![weapon(10, 2, &[])], vec![weapon(4, 2, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        let order: Vec<(&str, i32)> = log.iter().map(|s| (s.attacker.as_str(), s.damage)).collect();
        assert_eq!(order, vec![("a", 7), ("d", 3), ("a", 7), ("d", 3)]);
        assert_eq!((d.hp, a.hp), (26, 34));
    }

    #[test]
    fn defender_firststrike_strikes_before_the_attacker() {
        let rules = rules(60, vec![weapon(10, 1, &[])], vec![weapon(4, 1, &["firststrike"])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(log.iter().map(|s| s.attacker.as_str()).collect::<Vec<_>>(), vec!["d", "a"]);
    }

    #[test]
    fn a_killed_defender_cannot_retaliate_and_grants_kill_experience() {
        let rules = rules(60, vec![weapon(10, 1, &[])], vec![weapon(4, 3, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 5);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(log.len(), 1);
        assert_eq!((d.hp, a.hp), (0, 40));
        assert_eq!(a.xp, 8);
        assert_eq!((a.attacks_left, a.acted), (0, true));
    }

    #[test]
    fn drain_heals_from_the_actual_capped_hp_loss() {
        let mut drain = weapon(10, 1, &["drains"]);
        drain.drain_percent = Some(50);
        let rules = rules(100, vec![drain], vec![]);
        let mut a = unit("a", "A", 10);
        let mut d = unit("d", "D", 3);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(log[0].damage, 3);
        assert_eq!((a.hp, d.hp), (11, 0));
    }

    #[test]
    fn a_new_slow_changes_the_following_retaliation() {
        let rules = rules(100, vec![weapon(10, 1, &["slow"])], vec![weapon(10, 1, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(log[0].damage, 11);
        assert!(d.status.contains("slowed"));
        // Retaliation now uses S=ceil(3*10/4)=8 at 100%: 8*1.10 -> 9.
        assert_eq!(log[1].damage, 9);
    }
}
