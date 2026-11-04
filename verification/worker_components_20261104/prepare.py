"""Build diagnostics from an isolated copy of the exact integrated Rust and Lua sources."""
from pathlib import Path
from shutil import copy2,copytree,ignore_patterns
import sys

crate=Path(sys.argv[1]);here=Path(__file__).resolve().parent
copytree('engine_lite',crate,ignore=ignore_patterns('target','__pycache__'))
copy2(here/'cost.rs',crate/'src/cost.rs')

def edit(file,old,new,count=1):
    path=crate/file;text=path.read_text();assert text.count(old)==count,(file,old,text.count(old))
    path.write_text(text.replace(old,new))

edit('Cargo.toml','[dependencies]','[dependencies]\nlibc = "0.2"')
h='src/host.rs';lib='src/lib.rs';state='src/state.rs'
edit(lib,'use mlua::{','mod cost;\nuse mlua::{')
edit(h,'let lua=Lua::new();','''let lua=Lua::new();
    lua.globals().set("__cost_enter",lua.create_function(|_,key:String|{crate::cost::enter(key);Ok(())})?)?;
    lua.globals().set("__cost_leave",lua.create_function(|_,()|{crate::cost::leave();Ok(())})?)?;''')
edit(h,'let a:Value=lua.from_value(arg)?;', '''let _rpc=crate::cost::scope(format!("bridge.{op}"));
        let a:Value=crate::cost::timed(format!("bridge.{op}.arg"),||lua.from_value(arg))?;''')
edit(h,'let result=match op.as_str() {','let result={let _rust=crate::cost::scope(format!("bridge.{op}.rust")); match op.as_str() {')
edit(h,'};\n        lua.to_value(&result)','}};\n        crate::cost::timed(format!("bridge.{op}.to_lua"),||lua.to_value(&result))')
edit(h,'let public=g.public_units(side);','let public=crate::cost::timed("ref.public_units_for_rpc",||g.public_units(side));',2)
edit(h,'let mut copy=g.clone();','let mut copy=crate::cost::timed("ref.forecast_game_clone",||g.clone());')
edit(h,'let result=g.step(action).map_err(mlua::Error::external)?;',
     'let result=crate::cost::timed("ref.step",||g.step(action)).map_err(mlua::Error::external)?;')
for header,label in [('pub fn update_visibility(&mut self) {','ref.visibility'),
    ('pub fn observe(&self,s:usize)->Result<Value,String>{','ref.observe'),
    ('pub fn legal_actions(&self,s:usize)->Result<Vec<Action>,String> {','ref.legal_list'),
    ('pub(crate) fn reach_with_public(&self,u:&Unit,s:usize,public:&[Unit])->(Vec<u32>,Vec<usize>) {','ref.reach'),
    ('fn castle_slots(&self,s:usize)->BTreeSet<usize> {','ref.castle_slots')]:
    edit(state,header,header+f'\n        let _scope=crate::cost::scope("{label}");')
edit(lib,'fn observe(&self,side:usize)->PyResult<String>{encode','fn observe(&self,side:usize)->PyResult<String>{let _scope=cost::scope("python.observe");encode')
edit(lib,'fn observe_batch(&self,sides_json:&str)->PyResult<String>{','fn observe_batch(&self,sides_json:&str)->PyResult<String>{let _scope=cost::scope("audit.observe_batch");')
edit(lib,'let f:Function=self.lua.globals().get("lite_decision").map_err(error)?;',
     'let _direct=cost::scope(if score_only_astra {"python.astra_decision"}else{"python.policy_decision"});\n        let f:Function=self.lua.globals().get("lite_decision").map_err(error)?;')
edit(lib,'let result:mlua::Value=f.call((side,teacher,generate_candidates,score_only_astra,score_only_policy)).map_err(error)?;',
     'let result:mlua::Value=cost::timed("decision.lua",||f.call((side,teacher,generate_candidates,score_only_astra,score_only_policy))).map_err(error)?;')
edit(lib,'let a:Value=decode(action_json)?;',
     'let _direct=cost::scope(if score_only_astra {"python.astra_execute"}else{"python.policy_execute"});\n        let a:Value=cost::timed("execute.action_decode",||decode(action_json))?;')
edit(lib,'let result:mlua::Value=f.call((self.lua.to_value(&a).map_err(error)?,score_only_astra,policy_memory_write)).map_err(error)?;',
     'let input=cost::timed("execute.action_to_lua",||self.lua.to_value(&a)).map_err(error)?;\n        let result:mlua::Value=cost::timed("execute.lua",||f.call((input,score_only_astra,policy_memory_write))).map_err(error)?;')
p=crate/lib;source=p.read_text();old='let value:Value=self.lua.from_value(result).map_err(error)?;encode(&value)';assert source.count(old)==2
for name in ('decision','execute'):
    source=source.replace(old,f'''let value:Value=cost::timed("{name}.lua_to_value",||self.lua.from_value(result)).map_err(error)?;
        cost::timed("diag.sample_fields",||cost::payload(if score_only_astra {{"{name}.astra"}}else{{"{name}.policy"}},&value));
        cost::timed("{name}.json_encode",||encode(&value))''',1)
p.write_text(source)
edit(lib,'fn configure_host(&mut self,modules_json:&str)->PyResult<()> {','fn diagnostic_costs(&self)->String {cost::report()}\n    fn configure_host(&mut self,modules_json:&str)->PyResult<()> {')

lua='lua/host.lua';source=(crate/lua).read_text();at='local function require_module(path)'
assert source.count(at)==1
source=source.replace(at,(here/'wrap.lua').read_text()+'\n'+at)
old="local result=assert(load(source,'@'..name,'t',_ENV))();modules[name]=result;return result"
assert source.count(old)==1
source=source.replace(old,"""source=profile_locals(name,source)
    local result=assert(load(source,'@'..name,'t',_ENV))();profile_module(name,result);modules[name]=result;return result""")
source+='''\nrefresh=__timed('lua.refresh_public_view',refresh)
for _,key in ipairs {'find'} do wesnoth.map[key]=__timed('lua.map.'..key,wesnoth.map[key]) end
for _,key in ipairs {'find_reach','find_path'} do wesnoth.paths[key]=__timed('lua.paths.'..key,wesnoth.paths[key]) end
wesnoth.simulate_combat=__timed('lua.simulate_combat',wesnoth.simulate_combat)
for _,key in ipairs {'check_move','check_attack','check_recruit'} do ai[key]=__timed('lua.ai.'..key,ai[key]) end
'''
(crate/lua).write_text(source)
