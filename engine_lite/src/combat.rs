use crate::model::{Rules, Unit, Weapon};
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
pub struct Resolution {
    pub strikes: Vec<Strike>,
    pub defender_weapon: Option<usize>,
}

pub(super) fn resolved_weapon(rules:&Rules,unit:&Unit,index:usize)->Weapon {
    let mut weapon=rules.units[&unit.unit_type].weapons[index].clone();
    if let Some(&damage)=unit.resolved_weapon_damage.get(index){weapon.damage=damage;}
    weapon
}

/// Native rounding: half ties move towards the unmodified damage.
fn round_damage(damage:i64, bonus:i64, divisor:i64)->i64 {
    if damage==0 {return 0;}
    ( (damage*bonus+divisor/2-i64::from(bonus>=divisor))/divisor ).max(1)
}
#[cfg(test)]
pub fn slowed_damage(damage:i64)->i64 {round_damage(damage,1,2)}
pub(super) fn strike(rules:&Rules,a:&mut Unit,d:&mut Unit,w:&Weapon,
          opposing_weapon:Option<&Weapon>,terrain:&str,turn:u32,charging:bool,
          offense:bool,modifiers:&Modifiers,roll:u32)->Strike {
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
    let mut bonus=i64::from(100+tod+leadership)*i64::from(resist);
    if charging {bonus*=2;}
    if offense && modifiers.backstab && w.specials.contains("backstab") {bonus*=2;}
    let percent=opposing_weapon.and_then(|other|other.opponent_damage_percent).unwrap_or(100);
    let divisor=if a.status.contains("slowed") {2_000_000}else{1_000_000};
    let modified=round_damage(i64::from(w.damage),bonus*i64::from(percent),divisor);
    let connected=roll<chance;
    let dealt=if connected {modified.min(i64::from(d.hp)).max(0) as i32}else{0};
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
    Strike{attacker:a.id.clone(),defender:d.id.clone(),hit:connected,chance,damage:dealt,defender_hp:d.hp}
}
pub(super) fn kill_xp(level:u32)->u32 {if level==0 {4}else{8*level}}

pub fn resolve_seeded(rules:&Rules,a:&mut Unit,d:&mut Unit,weapon:usize,
    at:&str,dt:&str,turn:u32,modifiers:&Modifiers,rng:&mut u64)->Resolution {
    let aw=resolved_weapon(rules,a,weapon);
    let mut choices=rules.units[&d.unit_type].weapons.iter().enumerate()
        .filter(|(_,w)|w.range==aw.range).map(|(i,_)|i);
    let first=choices.next();
    let counter=if choices.next().is_none(){first}else{
        crate::combat_probability::select(rules,a,d,weapon,at,dt,turn,modifiers).0
    };
    resolve_with_counter(rules,a,d,&aw,counter,at,dt,turn,modifiers,&mut || roll_percent(rng))
}

/// SplitMix64 with rejection sampling, including seed zero. Referee-only state.
pub fn roll_percent(state:&mut u64)->u32 {
    loop {
        *state=state.wrapping_add(0x9e3779b97f4a7c15);
        let mut z=*state;
        z=(z^(z>>30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z=(z^(z>>27)).wrapping_mul(0x94d049bb133111eb);
        z^=z>>31;
        if z>=16 {return (z%100) as u32;}
    }
}

#[cfg(test)]
fn resolve(rules:&Rules,a:&mut Unit,d:&mut Unit,weapon:usize,
    at:&str,dt:&str,turn:u32,modifiers:&Modifiers)->Resolution {
    let (counter,_)=crate::combat_probability::select(rules,a,d,weapon,at,dt,turn,modifiers);
    let aw=resolved_weapon(rules,a,weapon);
    resolve_with_counter(rules,a,d,&aw,counter,at,dt,turn,modifiers,&mut || 0)
}

fn resolve_with_counter(rules:&Rules,a:&mut Unit,d:&mut Unit,aw:&Weapon,counter:Option<usize>,
               attacker_terrain:&str,defender_terrain:&str,turn:u32,modifiers:&Modifiers,roll:&mut impl FnMut()->u32)->Resolution {
    let dw=counter.map(|i|resolved_weapon(rules,d,i));
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
                if defense && n<dn { log.push(strike(rules,d,a,dw.as_ref().unwrap(),Some(&aw),attacker_terrain,turn,charge,false,modifiers,roll())); }
                if !defense && n<an { log.push(strike(rules,a,d,&aw,dw.as_ref(),defender_terrain,turn,charge,true,modifiers,roll())); }
            }
            if a.hp<=0 || d.hp<=0 || a.status.contains("petrified") || d.status.contains("petrified") { break; }
        }
        if a.hp<=0 || d.hp<=0 || a.status.contains("petrified") || d.status.contains("petrified") {break;}
    }
    let al=rules.units[&a.unit_type].level;let dl=rules.units[&d.unit_type].level;
    if a.hp>0 {a.xp+=if d.hp<=0 {kill_xp(dl)} else {dl};}
    if d.hp>0 {d.xp+=if a.hp<=0 {kill_xp(al)} else {al};}
    a.moves=0;a.attacks_left=a.attacks_left.saturating_sub(1);a.acted=true;
    Resolution{strikes:log,defender_weapon:counter}
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
        resolve(rules, attacker, defender, weapon_index, PLAIN, PLAIN, 1, &Modifiers::default()).strikes
            .into_iter().next().expect("one strike")
    }

    #[test]
    fn connected_strikes_use_full_damage_without_uplift() {
        let rules_60 = rules(60, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let hit = strike_once(&rules_60, &mut a, &mut d, 0);
        assert_eq!((hit.chance, hit.damage, hit.hit), (60, 10, true));
        assert_eq!(d.hp, 30);
        let rules_13 = rules(60, vec![weapon(13, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        assert_eq!(strike_once(&rules_13, &mut a, &mut d, 0).damage, 13);
        let rules_100 = rules(100, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        assert_eq!(strike_once(&rules_100, &mut a, &mut d, 0).damage, 10);
        let rules_1 = rules(1, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        assert_eq!(strike_once(&rules_1, &mut a, &mut d, 0).damage, 10);
    }

    #[test]
    fn slowed_damage_is_half_with_native_rounding() {
        let rules = rules(60, vec![weapon(10, 1, &[])], vec![]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        a.status.insert("slowed".into());
        let hit = strike_once(&rules, &mut a, &mut d, 0);
        assert_eq!((hit.damage, d.hp), (5, 35));
        assert_eq!(slowed_damage(10), 5);
        assert_eq!(slowed_damage(11), 6);
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
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        let order: Vec<(&str, i32)> = log.iter().map(|s| (s.attacker.as_str(), s.damage)).collect();
        assert_eq!(order, vec![("a", 10), ("d", 4), ("a", 10), ("d", 4)]);
        assert_eq!((d.hp, a.hp), (20, 32));
    }

    #[test]
    fn defender_firststrike_strikes_before_the_attacker() {
        let rules = rules(60, vec![weapon(10, 1, &[])], vec![weapon(4, 1, &["firststrike"])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        assert_eq!(log.iter().map(|s| s.attacker.as_str()).collect::<Vec<_>>(), vec!["d", "a"]);
    }

    #[test]
    fn a_killed_defender_cannot_retaliate_and_grants_kill_experience() {
        let rules = rules(60, vec![weapon(10, 1, &[])], vec![weapon(4, 3, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 5);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
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
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        assert_eq!(log[0].damage, 3);
        assert_eq!((a.hp, d.hp), (11, 0));
    }

    #[test]
    fn a_new_slow_changes_the_following_retaliation() {
        let rules = rules(100, vec![weapon(10, 1, &["slow"])], vec![weapon(10, 1, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        assert_eq!(log[0].damage, 10);
        assert!(d.status.contains("slowed"));
        assert_eq!(log[1].damage, 5);
    }

    #[test]
    fn retaliation_uses_the_opponents_resistance() {
        let mut hammer = weapon(10, 2, &[]);
        hammer.damage_type = "impact".into();
        let mut rules = rules(60, vec![weapon(1, 1, &[])], vec![weapon(7, 3, &[]), hammer]);
        rules.units.get_mut("A").unwrap().resistance =
            BTreeMap::from([("blade".into(), 40), ("impact".into(), 120)]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        let blows: Vec<i32> = log.iter().filter(|s| s.attacker == "d").map(|s| s.damage).collect();
        assert_eq!(blows, vec![12, 12]);
        assert_eq!(a.hp, 16);
    }

    #[test]
    fn retaliation_uses_terrain_and_magical_chance() {
        let rules = rules(10, vec![weapon(1, 1, &[])],
                          vec![weapon(10, 3, &[]), weapon(6, 3, &["magical"])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        assert!(log.iter().filter(|s| s.attacker == "d").all(|s| s.chance == 70));
        assert_eq!(a.hp, 22);
    }

    #[test]
    fn retaliation_uses_resolved_instance_damage() {
        let rules = rules(100, vec![weapon(1, 1, &[])],
                          vec![weapon(7, 3, &[]), weapon(8, 2, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        d.resolved_weapon_damage = vec![1, 10];
        resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(a.hp, 20);
    }

    #[test]
    fn retaliation_prefers_surviving_with_firststrike() {
        let rules = rules(100, vec![weapon(40, 1, &[])],
                          vec![weapon(20, 1, &[]), weapon(8, 1, &["firststrike"])]);
        let mut a = unit("a", "A", 8);
        let mut d = unit("d", "D", 20);
        let log = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default()).strikes;
        assert_eq!((a.hp, d.hp), (0, 20));
        assert_eq!(log[0].attacker, "d");
    }

    #[test]
    fn retaliation_compares_absorb_and_surviving_poison() {
        let mut absorb = weapon(6, 2, &[]);
        absorb.opponent_damage_percent = Some(50);
        let rules_absorb = rules(100, vec![weapon(10, 3, &[])],
                                 vec![weapon(10, 2, &[]), absorb]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        resolve(&rules_absorb, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!((a.hp, d.hp), (28, 25));
        let rules_poison = rules(100, vec![weapon(1, 1, &[])],
                                 vec![weapon(5, 2, &[]), weapon(4, 2, &["poison"])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        resolve(&rules_poison, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(a.hp, 32);
        assert!(a.status.contains("poisoned"));
    }

    #[test]
    fn retaliation_keeps_the_first_exact_tie_and_excludes_other_ranges() {
        let mut ranged = weapon(100, 4, &[]);
        ranged.range = "ranged".into();
        let rules = rules(60, vec![weapon(1, 1, &[])],
                          vec![ranged, weapon(4, 2, &[]), weapon(4, 2, &[])]);
        let mut a = unit("a", "A", 40);
        let mut d = unit("d", "D", 40);
        let outcome = resolve(&rules, &mut a, &mut d, 0, PLAIN, PLAIN, 1, &Modifiers::default());
        assert_eq!(outcome.defender_weapon, Some(1));
        assert_eq!(a.hp, 32);
    }
}
