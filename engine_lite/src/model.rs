//! Original compact rules representation. No code from the reference simulator.
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const ENGINE_VERSION: &str = "lite-0.1";
pub const RNG_VERSION: &str = "xoshiro256++-1";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Weapon {
    pub id: String,
    pub damage: i32,
    pub strikes: u32,
    pub damage_type: String,
    pub range: String,
    #[serde(default)] pub specials: BTreeSet<String>,
    #[serde(default)] pub plague_type: Option<String>,
    #[serde(default)] pub drain_percent: Option<u32>,
    #[serde(default)] pub opponent_damage_percent: Option<u32>,
    #[serde(default)] pub defense_cth_sub: u32,
    #[serde(default)] pub opponent_attacks: Option<u32>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct UnitType {
    pub id: String,
    pub scope: String,
    pub hp: i32,
    pub moves: u32,
    pub vision: u32,
    pub level: u32,
    pub cost: i32,
    pub experience: u32,
    pub alignment: String,
    #[serde(default)] pub advances_to: Vec<String>,
    #[serde(default)] pub weapons: Vec<Weapon>,
    /// Expanded, concrete terrain-code tables. Defense = percent chance to hit.
    pub movement: BTreeMap<String, u32>,
    pub defense: BTreeMap<String, u32>,
    pub resistance: BTreeMap<String, i32>,
    #[serde(default)] pub abilities: BTreeSet<String>,
    /// Native standard [heals] declarations share IDs at both +4 and +8.
    #[serde(default)] pub healing_amount: Option<i32>,
    #[serde(default)] pub healing_poison: Option<String>,
    #[serde(default)] pub healing_excluded_status: Option<String>,
    #[serde(default)] pub curing_unfiltered: bool,
    #[serde(default)] pub regeneration_amount: Option<i32>,
    #[serde(default)] pub regeneration_poison: Option<String>,
    #[serde(default)] pub regeneration_terrains: Option<BTreeSet<String>>,
    #[serde(default)] pub illumination: Option<i32>,
    #[serde(default)] pub concealment_terrains: BTreeSet<String>,
    #[serde(default)] pub concealment_requires_full_moves: bool,
    #[serde(default)] pub unsupported: Vec<String>,
    #[serde(default)] pub approximation_reasons: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Terrain {
    pub id: String,
    #[serde(default)] pub village: bool,
    #[serde(default)] pub castle: bool,
    #[serde(default)] pub keep: bool,
    #[serde(default)] pub healing: i32,
    #[serde(default)] pub concealment: BTreeSet<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Rules {
    pub source_version: String,
    pub rules_version: String,
    pub source_hash: String,
    pub units: BTreeMap<String, UnitType>,
    pub terrains: BTreeMap<String, Terrain>,
    #[serde(default = "default_tod")] pub lawful_bonus: Vec<i32>,
}
fn default_tod() -> Vec<i32> { vec![0,25,25,0,-25,-25] }

impl Rules {
    pub fn validate(&self) -> Result<(), String> {
        if self.source_version != "1.18.8" { return Err("rules must come from Wesnoth 1.18.8".into()); }
        if self.units.is_empty() || self.terrains.is_empty() || self.source_hash.is_empty() || self.lawful_bonus.is_empty() {
            return Err("incomplete rules tables or provenance".into());
        }
        let damage_types:BTreeSet<&str>=self.units.values().flat_map(|u|u.weapons.iter().map(|w|w.damage_type.as_str())).collect();
        for (id,u) in &self.units {
            if id != &u.id || u.hp <= 0 || u.experience == 0 { return Err(format!("invalid unit type {id}")); }
            for t in self.terrains.keys() {
                if !u.movement.contains_key(t) || !u.defense.contains_key(t) { return Err(format!("{id}: unexpanded terrain {t}")); }
                if u.defense[t] > 100 { return Err(format!("{id}: invalid defense {t}")); }
            }
            for kind in &damage_types {if !u.resistance.contains_key(*kind){return Err(format!("{id}: missing resistance {kind}"));}}
            for w in &u.weapons {
                if w.damage < 0 || w.strikes > 100 || !u.resistance.contains_key(&w.damage_type) {
                    return Err(format!("invalid weapon or resistance table: {id}/{}",w.id));
                }
                if let Some(p) = &w.plague_type { if !self.units.contains_key(p) { return Err(format!("missing plague type {p}")); } }
            }
            for a in &u.advances_to { if !self.units.contains_key(a) { return Err(format!("missing advancement {a}")); } }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Side {
    pub id: usize,
    pub team: String,
    pub gold: i32,
    #[serde(default = "base_income")] pub base_income: i32,
    #[serde(default)] pub recruit: Vec<String>,
    #[serde(default)] pub fog: bool,
    #[serde(default)] pub shroud: bool,
    #[serde(default)] pub share_view: bool,
    #[serde(default)] pub share_maps: bool,
    #[serde(default)] pub eliminated: bool,
}
fn base_income() -> i32 { 2 }

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Unit {
    pub id: String,
    pub unit_type: String,
    pub side: usize,
    pub pos: usize,
    pub hp: i32,
    pub moves: u32,
    pub attacks_left: u32,
    #[serde(default)] pub xp: u32,
    #[serde(default)] pub leader: bool,
    #[serde(default)] pub status: BTreeSet<String>,
    #[serde(default)] pub traits: BTreeSet<String>,
    #[serde(default)] pub acted: bool,
    /// The native standard feeding object adds one permanent max HP per kill.
    #[serde(default)] pub feeding_bonus: i32,
    /// Fully resolved trait/object statistics may be injected by native capture.
    /// The core never invents random traits from incomplete declarations.
    #[serde(default)] pub resolved_max_hp: Option<i32>,
    #[serde(default)] pub resolved_max_moves: Option<u32>,
    #[serde(default)] pub resolved_max_experience: Option<u32>,
    #[serde(default)] pub resolved_weapon_damage: Vec<i32>,
}
impl Unit {
    pub fn max_hp(&self,rules:&Rules)->i32{self.resolved_max_hp.unwrap_or(rules.units[&self.unit_type].hp)+self.feeding_bonus}
    pub fn max_moves(&self,rules:&Rules)->u32{self.resolved_max_moves.unwrap_or(rules.units[&self.unit_type].moves)}
    pub fn max_xp(&self,rules:&Rules)->u32{self.resolved_max_experience.unwrap_or(rules.units[&self.unit_type].experience)}
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameSpec {
    pub width: usize,
    pub height: usize,
    pub terrain: Vec<String>,
    pub sides: Vec<Side>,
    pub units: Vec<Unit>,
    #[serde(default)] pub village_owner: BTreeMap<usize,usize>,
    pub seed: u64,
    pub max_turns: u32,
    /// Explicit opt-in, recorded in snapshots and observations.
    #[serde(default)] pub allow_approximate: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(tag="kind", rename_all="snake_case")]
pub enum Action {
    EndTurn,
    Move { unit: String, to: usize, #[serde(default)] full: bool },
    Attack { unit: String, target: String, weapon: usize },
    Recruit { unit_type: String, to: usize },
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct SeenUnit { pub unit: Option<Unit>, pub turn: u32 }
#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct Knowledge {
    pub visible: Vec<bool>,
    pub explored: Vec<bool>,
    pub terrain: Vec<Option<String>>,
    pub villages: BTreeMap<usize,(usize,u32)>,
    pub enemies: BTreeMap<String,SeenUnit>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Random {
    pub state: [u64;4],
    #[serde(default)] pub injected_hits: Vec<bool>,
    #[serde(default)] pub injected_cursor: usize,
}
impl Random {
    pub fn new(mut seed: u64) -> Self {
        let mut state=[0;4];
        for s in &mut state {
            seed=seed.wrapping_add(0x9e3779b97f4a7c15);
            let mut z=seed; z=(z^(z>>30)).wrapping_mul(0xbf58476d1ce4e5b9);
            z=(z^(z>>27)).wrapping_mul(0x94d049bb133111eb); *s=z^(z>>31);
        }
        Self {state,injected_hits:vec![],injected_cursor:0}
    }
    pub fn next(&mut self) -> u64 {
        let s=&mut self.state;
        let result=s[0].wrapping_add(s[3]).rotate_left(23).wrapping_add(s[0]);
        let t=s[1]<<17;
        s[2]^=s[0];s[3]^=s[1];s[1]^=s[2];s[0]^=s[3];s[2]^=t;s[3]=s[3].rotate_left(45);
        result
    }
    pub fn hit(&mut self,chance:u32) -> bool {
        if self.injected_cursor < self.injected_hits.len() {
            let v=self.injected_hits[self.injected_cursor];self.injected_cursor+=1;return v;
        }
        // Rejection sampling avoids modulo bias and fixes the RNG contract.
        loop { let n=self.next(); if n < u64::MAX-u64::MAX%100 { return n%100 < chance as u64; } }
    }
}

pub fn neighbors(pos:usize,width:usize,height:usize) -> Vec<usize> {
    let x=(pos%width) as i32;let y=(pos/width) as i32;
    // Wesnoth odd-column offset coordinates, converted from 1-based x.
    let dy=if x%2==0 {-1} else {1};
    [(x,y-1),(x,y+1),(x-1,y),(x+1,y),(x-1,y+dy),(x+1,y+dy)]
        .into_iter().filter(|(a,b)| *a>=0 && *b>=0 && *a<width as i32 && *b<height as i32)
        .map(|(a,b)|b as usize*width+a as usize).collect()
}
