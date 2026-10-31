mod model;
mod combat;
mod state;
mod host;
#[cfg(test)] mod engine_tests;

use mlua::{Lua,LuaSerdeExt,Function};
use model::{Action,GameSpec,Rules,COMBAT_VERSION,ENGINE_VERSION,RNG_VERSION};
use pyo3::{exceptions::PyValueError,prelude::*};
use serde::{Deserialize,Serialize};
use serde_json::{json,Value};
use state::Game;
use std::sync::{Arc,Mutex};

fn error(e:impl ToString)->PyErr {PyValueError::new_err(e.to_string())}
fn decode<T:for<'de> Deserialize<'de>>(s:&str)->PyResult<T>{serde_json::from_str(s).map_err(error)}
fn encode<T:Serialize>(v:&T)->PyResult<String>{serde_json::to_string(v).map_err(error)}

/// Persistent Rust state and a directly embedded Lua VM. Methods return JSON
/// batches to avoid a Python callback for each hex, unit or combat prediction.
#[pyclass(unsendable)]
pub struct LiteEngine { game:Arc<Mutex<Game>>, lua:Lua, modules:std::collections::BTreeMap<String,String> }

impl LiteEngine {
    fn install_host(&mut self)->PyResult<()> {
        let modules=self.modules.clone();
        self.lua.globals().set("__module_sources",self.lua.to_value(&modules).map_err(error)?).map_err(error)?;
        self.lua.load(include_str!("../lua/host.lua")).set_name("lite_host").exec().map_err(error)
    }
}

#[pymethods]
impl LiteEngine {
    #[new]
    fn new(rules_json:&str,spec_json:&str)->PyResult<Self> {
        let rules:Rules=decode(rules_json)?;let spec:GameSpec=decode(spec_json)?;
        let game=Arc::new(Mutex::new(Game::new(Arc::new(rules),spec).map_err(error)?));
        let lua=host::create(game.clone()).map_err(error)?;
        Ok(Self{game,lua,modules:std::collections::BTreeMap::new()})
    }
    fn reset(&mut self,spec_json:&str)->PyResult<()> {
        let spec:GameSpec=decode(spec_json)?;
        let rules=self.game.lock().map_err(error)?.rules.clone();
        *self.game.lock().map_err(error)?=Game::new(rules,spec).map_err(error)?;
        self.lua=host::create(self.game.clone()).map_err(error)?;
        if !self.modules.is_empty(){self.install_host()?;}
        Ok(())
    }
    fn observe(&self,side:usize)->PyResult<String>{encode(&self.game.lock().map_err(error)?.observe(side).map_err(error)?)}
    fn observe_batch(&self,sides_json:&str)->PyResult<String>{
        let sides:Vec<usize>=decode(sides_json)?;let g=self.game.lock().map_err(error)?;
        let result:Result<Vec<Value>,String>=sides.into_iter().map(|s|g.observe(s)).collect();encode(&result.map_err(error)?)
    }
    fn legal_actions(&self,side:usize)->PyResult<String>{encode(&self.game.lock().map_err(error)?.legal_actions(side).map_err(error)?)}
    fn legal_batch(&self,sides_json:&str)->PyResult<String>{
        let sides:Vec<usize>=decode(sides_json)?;let g=self.game.lock().map_err(error)?;
        let result:Result<Vec<Vec<Action>>,String>=sides.into_iter().map(|s|g.legal_actions(s)).collect();encode(&result.map_err(error)?)
    }
    fn step(&mut self,action_json:&str)->PyResult<String>{
        let a:Action=decode(action_json)?;encode(&self.game.lock().map_err(error)?.step(a).map_err(error)?)
    }
    /// A batch is atomic: any invalid action restores the pre-batch state.
    fn step_batch(&mut self,actions_json:&str)->PyResult<String>{
        let actions:Vec<Action>=decode(actions_json)?;let mut g=self.game.lock().map_err(error)?;let saved=g.clone();
        let mut results=vec![];
        for a in actions {match g.step(a){Ok(v)=>results.push(v),Err(e)=>{*g=saved;return Err(error(e));}}}
        encode(&results)
    }
    fn snapshot(&self)->PyResult<String>{
        let g=self.game.lock().map_err(error)?;
        encode(&json!({"engine_id":ENGINE_VERSION,"rng_version":RNG_VERSION,"combat_version":COMBAT_VERSION,
            "game":&*g,"host":host::snapshot(&self.lua).map_err(error)?}))
    }
    fn restore(&mut self,snapshot_json:&str)->PyResult<()> {
        let value:Value=decode(snapshot_json)?;
        if value["engine_id"]!=ENGINE_VERSION || value["rng_version"]!=RNG_VERSION
            || value["combat_version"]!=COMBAT_VERSION {return Err(error("snapshot version mismatch"));}
        let g:Game=serde_json::from_value(value["game"].clone()).map_err(error)?;
        let expected=self.game.lock().map_err(error)?.rules.source_hash.clone();
        if g.rules.source_hash!=expected{return Err(error("snapshot rules hash mismatch"));}
        g.rules.validate().map_err(error)?;
        *self.game.lock().map_err(error)?=g;
        host::restore(&self.lua,value["host"].clone()).map_err(error)?;Ok(())
    }
    /// `samples` remains in the signature for existing callers and is ignored:
    /// one deterministic resolution replaces the former Monte Carlo estimate.
    #[pyo3(signature=(side,attacker,target,weapon,samples=128))]
    fn forecast(&self,side:usize,attacker:&str,target:&str,weapon:usize,samples:usize)->PyResult<String>{
        encode(&self.game.lock().map_err(error)?.forecast(side,attacker,target,weapon,samples).map_err(error)?)
    }
    /// Sources are caller-supplied repository Lua, generated features and the
    /// existing Astra archive. Lua sees the view-only bridge, never Game objects.
    fn configure_host(&mut self,modules_json:&str)->PyResult<()> {
        self.modules=decode(modules_json)?;
        self.install_host()
    }
    #[pyo3(signature=(side,teacher=false,generate_candidates=true))]
    fn decision(&mut self,side:usize,teacher:bool,generate_candidates:bool)->PyResult<String>{
        self.game.lock().map_err(error)?.side_check(side).map_err(error)?;
        host::set_side(&self.lua,side);
        let f:Function=self.lua.globals().get("lite_decision").map_err(error)?;
        let result:mlua::Value=f.call((side,teacher,generate_candidates)).map_err(error)?;
        let value:Value=self.lua.from_value(result).map_err(error)?;encode(&value)
    }
    fn execute_candidate(&mut self,action_json:&str)->PyResult<String>{
        let a:Value=decode(action_json)?;
        let f:Function=self.lua.globals().get("lite_execute").map_err(error)?;
        let result:mlua::Value=f.call(self.lua.to_value(&a).map_err(error)?).map_err(error)?;
        let value:Value=self.lua.from_value(result).map_err(error)?;encode(&value)
    }
}

#[pymodule]
fn _engine_lite(m:&Bound<'_,PyModule>)->PyResult<()> {
    m.add_class::<LiteEngine>()?;m.add("ENGINE_VERSION",ENGINE_VERSION)?;m.add("RNG_VERSION",RNG_VERSION)?;
    m.add("COMBAT_VERSION",COMBAT_VERSION)?;Ok(())
}
