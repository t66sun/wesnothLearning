//! Engine-level tests for the deterministic `expected_damage_v1` contract:
//! poison timing, slowed movement, seed independence and the point-mass forecast.
use crate::model::*;
use crate::state::{Game,POISON_TICK};
use std::collections::{BTreeMap,BTreeSet};
use std::sync::Arc;

const PLAIN: &str = "Gg";

fn weapon() -> Weapon {
    Weapon{id:"blade".into(),damage:10,strikes:1,damage_type:"blade".into(),range:"melee".into(),
        specials:BTreeSet::new(),plague_type:None,drain_percent:None,opponent_damage_percent:None,
        defense_cth_sub:0,opponent_attacks:None}
}

fn unit_type(id:&str)->UnitType {
    UnitType{id:id.into(),scope:"test".into(),hp:20,moves:5,vision:5,level:1,cost:10,
        experience:20,alignment:"neutral".into(),advances_to:vec![],weapons:vec![weapon()],
        movement:BTreeMap::from([(PLAIN.to_string(),1)]),
        defense:BTreeMap::from([(PLAIN.to_string(),60)]),
        resistance:BTreeMap::from([("blade".to_string(),100)]),
        abilities:BTreeSet::new(),healing_amount:None,healing_poison:None,healing_excluded_status:None,
        curing_unfiltered:false,regeneration_amount:None,regeneration_poison:None,
        regeneration_terrains:None,illumination:None,concealment_terrains:BTreeSet::new(),
        concealment_requires_full_moves:false,unsupported:vec![],approximation_reasons:vec![]}
}

fn rules()->Rules {
    let mut units=BTreeMap::new();
    for id in ["A","D"] {units.insert(id.to_string(),unit_type(id));}
    let mut terrains=BTreeMap::new();
    terrains.insert(PLAIN.to_string(),Terrain{id:PLAIN.into(),village:false,castle:false,keep:false,
        healing:0,concealment:BTreeSet::new()});
    Rules{source_version:"1.18.8".into(),rules_version:"test".into(),source_hash:"test".into(),
        units,terrains,lawful_bonus:vec![0]}
}

fn unit(id:&str,kind:&str,side:usize,pos:usize)->Unit {
    Unit{id:id.into(),unit_type:kind.into(),side,pos,hp:20,moves:5,attacks_left:1,xp:0,
        leader:false,status:BTreeSet::new(),traits:BTreeSet::new(),acted:true,feeding_bonus:0,
        resolved_max_hp:None,resolved_max_moves:None,resolved_max_experience:None,
        resolved_weapon_damage:vec![]}
}

fn side(id:usize)->Side {
    Side{id,team:id.to_string(),gold:100,base_income:2,recruit:vec![],fog:false,shroud:false,
        share_view:false,share_maps:false,eliminated:false}
}

fn spec(seed:u64)->GameSpec {
    let mut leader1=unit("l1","A",1,0);leader1.leader=true;
    let mut leader2=unit("l2","D",2,8);leader2.leader=true;
    GameSpec{width:3,height:3,terrain:vec![PLAIN.to_string();9],sides:vec![side(1),side(2)],
        units:vec![leader1,leader2,unit("u1","A",1,4),unit("u2","D",2,3)],
        village_owner:BTreeMap::new(),seed,max_turns:5,allow_approximate:true}
}

fn game(seed:u64)->Game {Game::new(Arc::new(rules()),spec(seed)).expect("valid game")}

fn hp(g:&Game,id:&str)->i32 {g.units[g.unit(id).expect(id)].hp}

#[test]
fn poison_ticks_six_on_its_own_turn_and_floors_at_one_hp() {
    let mut g=game(1);
    let i=g.unit("u1").unwrap();
    g.units[i].status.insert("poisoned".into());
    g.units[i].hp=10;
    // The other side's boundary never ticks the poisoned unit.
    g.end_turn();
    assert_eq!(hp(&g,"u1"),10);
    // Own turn, no rest because the unit already acted: 10-6 = 4.
    g.end_turn();
    assert_eq!(hp(&g,"u1"),4);
    g.end_turn();
    assert_eq!(hp(&g,"u1"),4);
    // Second own turn: rest is 2, poison is 6, so the floor keeps it alive at 1.
    g.end_turn();
    assert_eq!(POISON_TICK,6);
    assert_eq!(hp(&g,"u1"),1);
    assert!(g.units[g.unit("u1").unwrap()].status.contains("poisoned"));
}

#[test]
fn slow_doubles_movement_cost_until_the_side_boundary() {
    let mut g=game(1);
    let i=g.unit("u1").unwrap();
    g.units[i].status.insert("slowed".into());
    let u=g.units[i].clone();
    let (dist,_)=g.reach(&u,1);
    assert_eq!(dist[1],2);
    g.end_turn();
    assert!(!g.units[i].status.contains("slowed"));
    let u=g.units[i].clone();
    let (dist,_)=g.reach(&u,1);
    assert_eq!(dist[1],1);
}

#[test]
fn attack_damage_is_seed_independent() {
    let action=Action::Attack{unit:"u1".into(),target:"u2".into(),weapon:0};
    let mut first=game(1);let mut second=game(0xdead_beef);
    let one=first.step(action.clone()).expect("attack");
    let two=second.step(action).expect("attack");
    assert_eq!(one["strikes"],two["strikes"]);
    assert_eq!(hp(&first,"u2"),hp(&second,"u2"));
    // D=10 at 60%: ceil(10*60*1.10/100) = 7.
    assert_eq!(one["strikes"][0]["damage"],7);
    assert_eq!(one["strikes"][0]["chance"],60);
    assert_eq!(hp(&first,"u2"),13);
}

#[test]
fn forecast_is_a_single_point_mass_that_matches_the_resolved_battle() {
    let mut g=game(1);
    let before=(g.turn,g.revision,hp(&g,"u1"),hp(&g,"u2"));
    let view=g.forecast(1,"u1","u2",0,128).expect("forecast");
    assert_eq!(view["combat_version"],COMBAT_VERSION);
    assert_eq!(view["approximate"],false);
    assert_eq!(view["samples"],1);
    for who in ["attacker","defender"] {
        let chance=view[who]["hp_chance"].as_object().expect("point mass");
        assert_eq!(chance.len(),1);
        let (hp_key,probability)=chance.iter().next().unwrap();
        assert_eq!(*probability,1.0);
        assert_eq!(view[who]["average_hp"],hp_key.parse::<i32>().unwrap());
        assert!(view[who]["poisoned"].as_i64().is_some());
        assert!(view[who]["slowed"].as_i64().is_some());
    }
    // The query must not advance or mutate the game.
    assert_eq!((g.turn,g.revision,hp(&g,"u1"),hp(&g,"u2")),before);
    // Out-of-range sample counts stay accepted and ignored.
    assert_eq!(g.forecast(1,"u1","u2",0,0).unwrap()["samples"],1);
    assert_eq!(g.forecast(1,"u1","u2",0,100_000).unwrap()["samples"],1);
    // The prediction is the battle that actually happens.
    let predicted=view["defender"]["average_hp"].as_i64().unwrap() as i32;
    g.step(Action::Attack{unit:"u1".into(),target:"u2".into(),weapon:0}).expect("attack");
    assert_eq!(hp(&g,"u2"),predicted);
}
