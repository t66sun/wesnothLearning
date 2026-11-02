//! Seeded execution, public probability forecasts, poison and slow contracts.
use crate::model::*;
use crate::state::{Game,POISON_TICK};
use std::collections::{BTreeMap,BTreeSet};
use std::sync::Arc;

const PLAIN: &str = "Gg";

fn weapon() -> Weapon {
    Weapon{id:"blade".into(),damage:10,strikes:1,damage_type:"blade".into(),range:"melee".into(),accuracy:0,parry:0,attack_weight:1.,defense_weight:1.,
        specials:BTreeSet::new(),plague_type:None,drain_percent:None,opponent_damage_percent:None,
        defense_cth_sub:0,opponent_attacks:None}
}

fn unit_type(id:&str)->UnitType {
    UnitType{id:id.into(),scope:"test".into(),hp:20,moves:5,vision:5,level:1,cost:10,
        experience:20,alignment:"neutral".into(),advances_to:vec![],standard_amla:false,weapons:vec![weapon()],
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
        leader:false,status:BTreeSet::new(),traits:BTreeSet::new(),acted:true,feeding_bonus:0,amla_count:0,
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
fn poison_ticks_eight_on_its_own_turn_and_floors_at_one_hp() {
    let mut g=game(1);
    let i=g.unit("u1").unwrap();
    g.units[i].status.insert("poisoned".into());
    g.units[i].hp=10;
    // The other side's boundary never ticks the poisoned unit.
    g.end_turn();
    assert_eq!(hp(&g,"u1"),10);
    // Own turn, no rest because the unit already acted: 10-8 = 2.
    g.end_turn();
    assert_eq!(hp(&g,"u1"),2);
    g.end_turn();
    assert_eq!(hp(&g,"u1"),2);
    // Second own turn: rest is 2, poison is 8, so the floor keeps it alive at 1.
    g.end_turn();
    assert_eq!(POISON_TICK,8);
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
fn attack_damage_is_reproducible_for_the_same_seed() {
    let action=Action::Attack{unit:"u1".into(),target:"u2".into(),weapon:0};
    let mut first=game(1);let mut second=game(1);
    assert_eq!(first.step(action.clone()).unwrap(),second.step(action).unwrap());
}

#[test]
fn forecast_distribution_contains_the_resolved_battle() {
    let mut g=game(1);
    let before=serde_json::to_value(&g).unwrap();
    let view=g.forecast(1,"u1","u2",0,128).unwrap();
    assert_eq!(view["combat_version"],COMBAT_VERSION);
    assert_eq!(view["approximate"],false);
    assert_eq!(view["samples"],0);
    assert_eq!(serde_json::to_value(&g).unwrap(),before);
    for samples in [0,100_000] {assert_eq!(view,g.forecast(1,"u1","u2",0,samples).unwrap());}
    g.step(Action::Attack{unit:"u1".into(),target:"u2".into(),weapon:0}).unwrap();
    for (who,id) in [("attacker","u1"),("defender","u2")] {
        assert!(view[who]["hp_chance"][hp(&g,id).to_string()].as_f64().unwrap()>0.);
    }
}

#[test]
fn probabilistic_forecast_preserves_state() {
    let g=game(1);
    let before=serde_json::to_value(&g).unwrap();
    let f=g.forecast(1,"u1","u2",0,128).unwrap();
    for who in ["attacker","defender"] {
        assert!((f[who]["average_hp"].as_f64().unwrap()-14.0).abs()<1e-12);
        assert!((f[who]["hp_chance"]["10"].as_f64().unwrap()-0.6).abs()<1e-12);
        assert!((f[who]["hp_chance"]["20"].as_f64().unwrap()-0.4).abs()<1e-12);
    }
    assert_eq!(serde_json::to_value(&g).unwrap(),before);
    assert_eq!(f,game(999).forecast(1,"u1","u2",0,1).unwrap());
}

#[test]
fn probabilistic_execution_restores_same_future() {
    let action=Action::Attack{unit:"u1".into(),target:"u2".into(),weapon:0};
    let mut outcomes=BTreeSet::new();
    for seed in 0..64 {
        let mut a=game(seed);
        let mut b:Game=serde_json::from_value(serde_json::to_value(&a).unwrap()).unwrap();
        a.forecast(1,"u1","u2",0,128).unwrap();
        let one=a.step(action.clone()).unwrap();
        assert_eq!(one,b.step(action.clone()).unwrap());
        let damage=one["strikes"][0]["damage"].as_i64().unwrap();
        assert!(damage==0 || damage==10);
        outcomes.insert(damage);
    }
    assert_eq!(outcomes,BTreeSet::from([0,10]));
}
