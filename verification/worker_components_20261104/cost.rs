// Used only in the isolated profiling crate.
use serde::Serialize;
use std::{cell::RefCell, collections::BTreeMap, time::Instant};

#[derive(Default, Serialize)]
struct Metric { calls:u64, wall_ns:u64, cpu_ns:u64, self_wall_ns:u64, self_cpu_ns:u64 }
struct Frame { name:String, wall:Instant, cpu:u64, child_wall:u64, child_cpu:u64 }
#[derive(Default)]
struct Data {
    stack:Vec<Frame>, totals:BTreeMap<String,Metric>, edges:BTreeMap<String,Metric>,
    samples:BTreeMap<String,(u64,BTreeMap<String,u64>)>,
}
thread_local! { static DATA:RefCell<Data> = RefCell::new(Data::default()); }

fn cpu() -> u64 {
    let mut t=libc::timespec{tv_sec:0,tv_nsec:0};
    assert_eq!(unsafe{libc::clock_gettime(libc::CLOCK_THREAD_CPUTIME_ID,&mut t)},0);
    (t.tv_sec as u64)*1_000_000_000+(t.tv_nsec as u64)
}
pub fn enter(name:impl Into<String>) {
    let frame=Frame{name:name.into(),wall:Instant::now(),cpu:cpu(),child_wall:0,child_cpu:0};
    DATA.with(|d|d.borrow_mut().stack.push(frame));
}
pub fn leave() {
    let end=Instant::now();let cpu_end=cpu();
    DATA.with(|d|{
        let mut d=d.borrow_mut();let frame=d.stack.pop().expect("paired trace scope");
        let wall=(end-frame.wall).as_nanos() as u64;let cpu=cpu_end-frame.cpu;
        let edge=if let Some(parent)=d.stack.last_mut(){
            parent.child_wall+=wall;parent.child_cpu+=cpu;
            format!("{} > {}",parent.name,frame.name)
        }else{format!("root > {}",frame.name)};
        let add=|m:&mut Metric|{
            m.calls+=1;m.wall_ns+=wall;m.cpu_ns+=cpu;
            m.self_wall_ns+=wall.saturating_sub(frame.child_wall);
            m.self_cpu_ns+=cpu.saturating_sub(frame.child_cpu);
        };
        add(d.totals.entry(frame.name).or_default());add(d.edges.entry(edge).or_default());
    });
}
pub struct Guard;
impl Drop for Guard {fn drop(&mut self){leave();}}
pub fn scope(name:impl Into<String>)->Guard {enter(name);Guard}
pub fn timed<T>(name:impl Into<String>,f:impl FnOnce()->T)->T {let _g=scope(name);f()}

pub fn payload(label:&str,value:&serde_json::Value) {
    DATA.with(|d|{
        let mut d=d.borrow_mut();let (count,sizes)=d.samples.entry(label.into()).or_default();
        *count+=1;
        if (*count-1)%64==0 {
            if let Some(fields)=value.as_object() {for (k,v) in fields {
                *sizes.entry(k.clone()).or_default()+=serde_json::to_vec(v).unwrap().len() as u64;
            }}
        }
    });
}
pub fn report()->String {
    DATA.with(|d|{let d=d.borrow();assert!(d.stack.is_empty());
        serde_json::json!({"scopes":d.totals,"edges":d.edges,"payloads":d.samples}).to_string()})
}
