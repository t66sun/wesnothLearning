use mlua::{HookTriggers, Lua, Result, VmState};
use std::{cell::Cell, time::{Duration, Instant}};

#[derive(Clone, Copy, Default)]
struct Limits { deadline: Option<Instant>, read_only: bool }

pub fn install(lua: &Lua) {
    lua.set_app_data(Cell::new(Limits::default()));
    lua.set_hook(HookTriggers::new().every_nth_instruction(1000), |lua, _| {
        check(lua)?;
        Ok(VmState::Continue)
    });
}

fn duration(seconds: f64) -> Result<Duration> {
    if !seconds.is_finite() || seconds <= 0. || seconds > 3600. {
        return Err(mlua::Error::external("invalid Lua call budget"));
    }
    Ok(Duration::from_secs_f64(seconds))
}

pub fn check(lua: &Lua) -> Result<()> {
    if lua.app_data_ref::<Cell<Limits>>().unwrap().get().deadline.is_some_and(|d| Instant::now() > d) {
        return Err(mlua::Error::external("Lua hard deadline exceeded"));
    }
    Ok(())
}

pub fn writable(lua: &Lua) -> Result<()> {
    check(lua)?;
    if lua.app_data_ref::<Cell<Limits>>().unwrap().get().read_only {
        return Err(mlua::Error::external("teacher planning cannot execute actions"));
    }
    Ok(())
}

pub fn begin(lua: &Lua, seconds: f64) -> Result<()> {
    let budget = duration(seconds)?;
    let state = lua.app_data_ref::<Cell<Limits>>().unwrap();
    if state.get().deadline.is_some() { return Err(mlua::Error::external("Lua call already active")); }
    state.set(Limits { deadline: Some(Instant::now()+budget), read_only: false });
    Ok(())
}

pub fn finish(lua: &Lua, enforce: bool) -> Result<()> {
    let result = if enforce { check(lua) } else { Ok(()) };
    lua.app_data_ref::<Cell<Limits>>().unwrap().set(Limits::default());
    result
}

pub fn planning<T>(lua: &Lua, run: impl FnOnce() -> Result<T>) -> Result<T> {
    let original = lua.app_data_ref::<Cell<Limits>>().unwrap().get();
    lua.app_data_ref::<Cell<Limits>>().unwrap().set(Limits { read_only: true, ..original });
    let result = check(lua).and_then(|_| run()).and_then(|value| { check(lua)?; Ok(value) });
    lua.app_data_ref::<Cell<Limits>>().unwrap().set(original);
    result
}

pub fn query<T>(lua: &Lua, seconds: f64, run: impl FnOnce() -> Result<T>) -> Result<T> {
    check(lua)?;
    let budget = duration(seconds)?;
    let original = lua.app_data_ref::<Cell<Limits>>().unwrap().get();
    let started = Instant::now();
    lua.app_data_ref::<Cell<Limits>>().unwrap().set(Limits { deadline: Some(started+budget), read_only: true });
    let result = run().and_then(|value| { check(lua)?; Ok(value) });
    let elapsed = started.elapsed();
    lua.app_data_ref::<Cell<Limits>>().unwrap().set(Limits {
        deadline: original.deadline.map(|d| d+elapsed), ..original
    });
    result
}
