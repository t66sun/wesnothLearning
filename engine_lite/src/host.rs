use crate::{model::*,state::Game};
use mlua::{Lua,LuaSerdeExt,Function,Value as LuaValue};
use serde_json::{json,Value};
use std::{cell::Cell,sync::{Arc,Mutex},time::Instant};

pub fn create(game:Arc<Mutex<Game>>)->mlua::Result<Lua> {
    let lua=Lua::new();let started=Instant::now();
    lua.set_app_data(Cell::new(1usize));
    lua.globals().set("__clock_ms",lua.create_function(move |_,()|Ok(started.elapsed().as_millis() as u64))?)?;
    lua.globals().set("__bridge",lua.create_function(move |lua,(op,arg):(String,LuaValue)| {
        let a:Value=lua.from_value(arg)?;
        let mut g=game.lock().map_err(|e|mlua::Error::external(e.to_string()))?;
        let side=lua.app_data_ref::<Cell<usize>>().unwrap().get();
        if a["side"].as_u64().is_some_and(|s|s as usize!=side){return Err(mlua::Error::external("host cannot switch player views"));}
        g.side_check(side).map_err(mlua::Error::external)?;
        let result=match op.as_str() {
            "view"=>g.observe(side).map_err(mlua::Error::external)?,
            "reward_labels"=>g.reward_labels(side),
            "rules"=>json!({"units":g.rules.units,"terrains":g.rules.terrains,"lawful_bonus":g.rules.lawful_bonus}),
            "legal"=>json!(g.legal_actions(side).map_err(mlua::Error::external)?),
            "reach"|"path"=>{
                let id=a["id"].as_str().ok_or_else(||mlua::Error::external("missing visible unit ID"))?;
                let mut u=g.public_units(side).into_iter().find(|u|u.id==id).ok_or_else(||mlua::Error::external("unit is not visible"))?;
                let max_moves=u.max_moves(&g.rules);
                u.moves=if op=="path" {(g.spec.terrain.len() as u32).saturating_mul(100)} else {a["moves"].as_u64().unwrap_or(u.moves as u64).min(max_moves as u64) as u32};
                let (dist,prev)=g.reach(&u,side);
                if op=="reach" {
                    json!(dist.into_iter().enumerate().filter(|(_,d)|*d<=u.moves).map(|(p,d)|json!([p,u.moves-d])).collect::<Vec<_>>())
                } else {
                    let to=a["to"].as_u64().unwrap_or(usize::MAX as u64) as usize;
                    if to>=prev.len() || prev[to]==usize::MAX {json!({"path":[],"cost":null})}
                    else {let mut p=to;let mut path=vec![p];while p!=u.pos {p=prev[p];path.push(p);}path.reverse();json!({"path":path,"cost":dist[to]})}
                }
            },
            "forecast"=>{
                let attacker=a["attacker"].as_str().ok_or_else(||mlua::Error::external("missing attacker"))?;
                let target=a["target"].as_str().ok_or_else(||mlua::Error::external("missing target"))?;
                let public=g.public_units(side);
                if !public.iter().any(|u|u.id==attacker) || !public.iter().any(|u|u.id==target) {return Err(mlua::Error::external("forecast uses an unseen unit"));}
                let pos=a["pos"].as_u64().ok_or_else(||mlua::Error::external("missing combat location"))? as usize;
                if pos>=g.spec.terrain.len() || g.knowledge[side-1].terrain[pos].is_none() {return Err(mlua::Error::external("forecast terrain is unknown"));}
                let mut copy=g.clone();let i=copy.unit(attacker).unwrap();copy.units[i].pos=pos;
                copy.forecast(side,attacker,target,a["weapon"].as_u64().unwrap_or(0) as usize,128).map_err(mlua::Error::external)?
            },
            "step"=>{
                if side!=g.current{return Err(mlua::Error::external("cannot act for another side"));}
                let action:Action=serde_json::from_value(a["action"].clone()).map_err(mlua::Error::external)?;
                let result=g.step(action).map_err(mlua::Error::external)?;
                json!({"result":result,"view":g.observe(side).map_err(mlua::Error::external)?})
            },
            _=>return Err(mlua::Error::external(format!("unknown host operation {op}"))),
        };
        lua.to_value(&result)
    })?)?;
    Ok(lua)
}
pub fn set_side(lua:&Lua,side:usize) {lua.app_data_ref::<Cell<usize>>().unwrap().set(side);}
pub fn snapshot(lua:&Lua)->mlua::Result<Value> {
    match lua.globals().get::<Option<Function>>("lite_snapshot")? {
        Some(f)=>lua.from_value(f.call::<LuaValue>(())?),None=>Ok(Value::Null)
    }
}
pub fn restore(lua:&Lua,value:Value)->mlua::Result<()> {
    if !value.is_null() {let f:Function=lua.globals().get("lite_restore")?;f.call::<()>(lua.to_value(&value)?)?;}
    Ok(())
}
