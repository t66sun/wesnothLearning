//! Seeded execution, public probability forecasts, poison and slow contracts.
use crate::model::*;
use crate::state::{Game,POISON_TICK};
use std::collections::{BTreeMap,BTreeSet};
use std::sync::Arc;

const PLAIN: &str = "Gg";
thread_local! { pub(crate) static NEIGHBOR_CALLS: std::cell::Cell<usize> = const { std::cell::Cell::new(0) }; }
thread_local! { pub(crate) static REACH_SEARCHES: std::cell::Cell<usize> = const { std::cell::Cell::new(0) }; }

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

fn intent_fixture() -> Game {
    let mut catalog=rules();
    let keep=catalog.terrains.get_mut(PLAIN).unwrap();keep.castle=true;keep.keep=true;
    let mut board=spec(7);
    board.sides[0].recruit.push("A".into());
    Game::new(Arc::new(catalog),board).unwrap()
}

#[test]
fn step_searches_only_the_moving_actor_once() {
    let game=intent_fixture();
    let listed=game.legal_actions(1).unwrap();
    let mut observed=vec![];
    for intent in [Action::EndTurn,
        listed.iter().find(|a|matches!(a,Action::Move{..})).unwrap().clone(),
        listed.iter().find(|a|matches!(a,Action::Attack{..})).unwrap().clone(),
        listed.iter().find(|a|matches!(a,Action::Recruit{..})).unwrap().clone()] {
        let mut copy=game.clone();
        REACH_SEARCHES.with(|c|c.set(0));
        copy.step(intent).unwrap();
        observed.push(REACH_SEARCHES.with(|c|c.get()));
    }
    assert_eq!(observed, [0,1,0,0], "end, move, attack, recruit");
}

#[test]
fn step_accepts_exactly_the_public_intents_and_rejects_without_mutation() {
    let mut game=intent_fixture();
    game.units[0].attacks_left=0;
    game.units[3].status.insert("petrified".into());
    let listed=game.legal_actions(1).unwrap();
    let before=serde_json::to_value(&game).unwrap();
    let ids=["l1","l2","u1","u2","missing"];
    let mut intents=vec![Action::EndTurn];
    for to in (0..=game.spec.terrain.len()).chain(std::iter::once(usize::MAX)) {
        for id in ids {
            for full in [false,true] {intents.push(Action::Move{unit:id.into(),to,full});}
        }
        for name in ["A","D","missing"] {intents.push(Action::Recruit{unit_type:name.into(),to});}
    }
    for unit in ids {for target in ids {for weapon in 0..2 {
        intents.push(Action::Attack{unit:unit.into(),target:target.into(),weapon});
    }}}
    for intent in intents {
        let mut canonical=intent.clone();
        if let Action::Move{full,..}=&mut canonical {*full=false;}
        let mut copy=game.clone();
        let actual=copy.step(intent.clone());
        assert_eq!(actual.is_ok(),listed.contains(&canonical),"{intent:?}");
        if let Err(error)=actual {
            assert_eq!(error,"action is absent from the player's legal intents");
            assert_eq!(serde_json::to_value(&copy).unwrap(),before,"{intent:?}");
        }
    }
}

#[test]
fn reach_expands_local_neighbors_once_and_charges_adjacent_village_terrain() {
    let mut g = game(1);
    for other in g.units.iter_mut().skip(1) { other.hp = 0; }
    let walker = g.units[0].clone();
    let kind = Arc::make_mut(&mut g.rules).units.get_mut(&walker.unit_type).unwrap();
    kind.abilities.insert("teleport".into());
    kind.movement.insert(PLAIN.into(), 2);
    g.knowledge[0].villages = BTreeMap::from([(0,(1,1)), (1,(1,1)), (8,(1,1))]);
    NEIGHBOR_CALLS.with(|n| n.set(0));
    let (distance, predecessor) = g.reach(&walker, 1);
    assert_eq!((distance[1], predecessor[1]), (2,0)); // adjacent owned village
    assert_eq!((distance[8], predecessor[8]), (1,0)); // remote owned village
    let reached = distance.iter().filter(|&&d| d != u32::MAX).count();
    assert_eq!(NEIGHBOR_CALLS.with(|n| n.get()), reached);
}

#[test]
fn terrain_vision_reuses_only_unchanged_origins_and_types() {
    let mut catalog = rules();
    catalog.units.get_mut("A").unwrap().vision = 1;
    let mut board = spec(7);
    for side in &mut board.sides { side.fog = true; side.shroud = true; }
    let mut game = Game::new(Arc::new(catalog), board).unwrap();
    let alive = game.units.iter().filter(|u| u.hp > 0).count();
    assert_eq!(game.vision_searches(), alive);
    let snapshot = serde_json::to_value(&game).unwrap();
    assert!(snapshot.get("vision").is_none());
    let mut restored: Game = serde_json::from_value(snapshot).unwrap();
    assert_eq!(restored.vision_searches(), 0);
    assert_eq!(game.clone().vision_searches(), 0);
    let mut searches = alive;
    for change in ["stationary", "move", "advance", "die", "replace"] {
        for state in [&mut game, &mut restored] {
            match change {
                "move" => state.units[0].pos = 1,
                "advance" => state.units[0].unit_type = "D".to_string(),
                "die" => state.units[0].hp = 0,
                "replace" => state.units[0].hp = 1,
                _ => (),
            }
            state.update_visibility();
        }
        searches += usize::from(matches!(change, "move" | "advance" | "replace"));
        assert_eq!(game.vision_searches(), searches, "{change}");
        assert_eq!(serde_json::to_value(&game).unwrap(), serde_json::to_value(&restored).unwrap(), "{change}");
        // Make the reference recompute all footprints at every boundary.
        restored = game.clone();
    }
}

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
