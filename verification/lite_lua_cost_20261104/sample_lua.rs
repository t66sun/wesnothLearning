// Compiled only in the isolated diagnostic build created by build_sampler.py.
use std::{cell::RefCell, collections::BTreeMap, path::PathBuf};
use mlua::{HookTriggers, Lua, VmState};

struct Samples {
    output: PathBuf,
    stacks: BTreeMap<String, u64>,
}

impl Drop for Samples {
    fn drop(&mut self) {
        let file = std::fs::File::create_new(&self.output).expect("fresh Lua sample destination");
        serde_json::to_writer(file, &self.stacks).expect("write Lua samples");
    }
}

pub fn install(lua: &Lua) {
    let output = std::env::var_os("LITE_LUA_SAMPLE_FILE").expect("set diagnostic output");
    let samples = RefCell::new(Samples {output: output.into(), stacks: BTreeMap::new()});
    lua.set_hook(HookTriggers::new().every_nth_instruction(50_003), move |lua, frame| {
        let mut stack = Vec::new();
        let source = frame.source();
        stack.push(format!("{}:{}:{}", source.short_src.as_deref().unwrap_or("?"),
                           source.line_defined.unwrap_or(0), frame.curr_line()));
        for depth in 1..12 {
            let Some(parent) = lua.inspect_stack(depth) else {break};
            let source = parent.source();
            stack.push(format!("{}:{}", source.short_src.as_deref().unwrap_or("?"),
                               source.line_defined.unwrap_or(0)));
        }
        *samples.borrow_mut().stacks.entry(stack.join("|")).or_default() += 1;
        Ok(VmState::Continue)
    });
}
