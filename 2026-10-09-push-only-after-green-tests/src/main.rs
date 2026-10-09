//! Three ways to enforce "push only after a green test run in the last 15 minutes"
//! on a coding agent's tool calls, run against the same fake event traces.
//!
//! A  stateless gate: decides from the push request alone (it can only trust
//!    a `tests_passed` claim the agent puts in the request).
//! B  in-memory gate: the harness remembers the last test result and its time
//!    in a variable. No disk. Typical hand-written code.
//! C  Dogwood Local Engine: the temporal policy from the AWS post, durable store.
//!
//! No tool runs. No network calls. The clock is injected so a "17 minutes later"
//! step does not need real waiting.

use dogwood_language::{Event, EventBuilder, Value};
use dogwood_local_engine::{
    Clock, DurableConfig, DurableTemporalEngine, Outcome, PolicyToken, Verb,
};
use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::{AtomicI64, Ordering};
use std::time::Instant;

const SCHEMA: &str = r#"
namespace Sandbox {
  entity Agent;
  entity Box;
  type TestInput  = { suite: String };
  type TestOutput = { passed: Bool };
  type PushInput  = { ref: String, tests_passed: Bool };
  action "tests" appliesTo {
    principal: [Agent], resource: [Box],
    context: { input: TestInput, output?: TestOutput }
  };
  action "git:push" appliesTo {
    principal: [Agent], resource: [Box],
    context: { input: PushInput }
  };
  type ReadInput = { path: String };
  action "read_file" appliesTo {
    principal: [Agent], resource: [Box],
    context: { input: ReadInput }
  };
}
"#;

const RUN_TESTS: &str = r#"
@id("run_tests")
permit (principal, action == Sandbox::Action::"tests", resource);
@id("read_files")
permit (principal, action == Sandbox::Action::"read_file", resource);
"#;

fn push_policy(window: &str) -> String {
    format!(
        r#"
@id("push_after_green_tests")
permit (principal, action == Sandbox::Action::"git:push", resource)
when temporal {{
    !Sandbox::Action::"tests"::response{{ output.passed: false }}
    since within {window}
    Sandbox::Action::"tests"::response{{ output.passed: true }}
}};
"#
    )
}

const SEC: i64 = 1_000_000_000;
const T0: i64 = 1_790_000_000 * SEC; // fixed epoch for reproducibility

#[derive(Clone)]
struct ManualClock(Arc<AtomicI64>);
impl Clock for ManualClock {
    fn now_nanos(&self) -> i64 {
        self.0.load(Ordering::SeqCst)
    }
}

fn base(action: &str, kind: &str) -> EventBuilder {
    Event::builder(&format!("Sandbox::Action::{action}"), kind)
        .principal("Sandbox::Agent::\"coder\"")
        .resource("Sandbox::Box::\"repo\"")
}
fn tests_req() -> EventBuilder {
    base("tests", "request").field("input", "suite", Value::String("unit".into()))
}
fn tests_resp(passed: bool) -> EventBuilder {
    base("tests", "response")
        .field("input", "suite", Value::String("unit".into()))
        .field("output", "passed", Value::Bool(passed))
}
fn read_req() -> EventBuilder {
    base("read_file", "request").field("input", "path", Value::String("src/lib.rs".into()))
}
fn push_req(claim: bool) -> EventBuilder {
    base("git:push", "request")
        .field("input", "ref", Value::String("refs/heads/fix".into()))
        .field("input", "tests_passed", Value::Bool(claim))
        .request_context("input", "ref", Value::String("refs/heads/fix".into()))
        .request_context("input", "tests_passed", Value::Bool(claim))
}

#[derive(Clone, Debug)]
enum Step {
    At(i64),            // set clock to T0 + secs
    Tests(bool),        // tests request + response(passed)
    Push { claim: bool },
    Restart,            // drop every gate's process state, reopen the store
    Reinstall(String),  // owner re-applies the policy set with install()
    UpdatePush(String), // owner changes only the push policy with batch(Update)
}

// ---- gate B: in-memory, hand-written ----
#[derive(Default)]
struct MemGate {
    last: Option<(bool, i64)>, // (passed, ts)
    window_ns: i64,
}
impl MemGate {
    fn record(&mut self, passed: bool, ts: i64) {
        self.last = Some((passed, ts));
    }
    fn push(&self, now: i64) -> bool {
        matches!(self.last, Some((true, ts)) if now - ts <= self.window_ns)
    }
}

struct Run {
    clock: Arc<AtomicI64>,
    path: PathBuf,
    engine: DurableTemporalEngine,
    push_token: Option<PolicyToken>,
    mem: MemGate,
}

fn open(path: &PathBuf, clock: &Arc<AtomicI64>) -> DurableTemporalEngine {
    DurableTemporalEngine::open_with_config(
        path,
        DurableConfig::new(0).with_clock(Box::new(ManualClock(clock.clone()))),
    )
    .expect("open store")
}

fn decide(engine: &mut DurableTemporalEngine, ev: EventBuilder) -> bool {
    match engine.submit(ev).expect("submit").outcome {
        Outcome::Decision(d) => d.allowed(),
        Outcome::Recorded => panic!("request without verdict"),
    }
}

fn token_for_push(engine: &DurableTemporalEngine) -> Option<PolicyToken> {
    engine
        .list()
        .into_iter()
        .find(|e| e.statement.contains("git:push"))
        .map(|e| e.token.clone())
}

impl Run {
    fn new(tag: &str) -> Self {
        let path = std::env::temp_dir().join(format!("pushgate-{tag}-{}.redb", std::process::id()));
        let _ = std::fs::remove_file(&path);
        let clock = Arc::new(AtomicI64::new(T0));
        let mut engine = open(&path, &clock);
        engine
            .install(&format!("{RUN_TESTS}{}", push_policy("15m")), SCHEMA, None, None)
            .expect("install");
        let push_token = token_for_push(&engine);
        Run { clock, path, engine, push_token, mem: MemGate { last: None, window_ns: 15 * 60 * SEC } }
    }
    fn now(&self) -> i64 {
        self.clock.load(Ordering::SeqCst)
    }
    /// returns Some((A, B, C)) for a push, None otherwise
    fn step(&mut self, s: &Step) -> Option<(bool, bool, bool)> {
        match s {
            Step::At(secs) => {
                self.clock.store(T0 + secs * SEC, Ordering::SeqCst);
                None
            }
            Step::Tests(p) => {
                assert!(decide(&mut self.engine, tests_req()));
                self.engine.submit(tests_resp(*p)).expect("resp");
                let now = self.now();
                self.mem.record(*p, now);
                None
            }
            Step::Push { claim } => {
                let a = *claim; // stateless: trusts the request
                let b = self.mem.push(self.now());
                let c = decide(&mut self.engine, push_req(*claim));
                Some((a, b, c))
            }
            Step::Restart => {
                let window = self.mem.window_ns;
                self.mem = MemGate { last: None, window_ns: window };
                let path = self.path.clone();
                // drop the engine (process exit), then reopen the same store
                let placeholder = open(&std::env::temp_dir().join(format!("pushgate-tmp-{}.redb", std::process::id())), &self.clock);
                let old = std::mem::replace(&mut self.engine, placeholder);
                drop(old);
                self.engine = open(&path, &self.clock);
                None
            }
            Step::Reinstall(window) => {
                self.engine
                    .install(&format!("{RUN_TESTS}{}", push_policy(window)), SCHEMA, None, None)
                    .expect("reinstall");
                self.push_token = token_for_push(&self.engine);
                None
            }
            Step::UpdatePush(window) => {
                let id = self.push_token.clone().expect("push token");
                self.engine
                    .batch(vec![Verb::Update { id, policy: push_policy(window) }])
                    .expect("update");
                self.push_token = token_for_push(&self.engine);
                None
            }
        }
    }
}

fn v(b: bool) -> &'static str {
    if b { "ALLOW" } else { "DENY" }
}

fn traces() -> Vec<(&'static str, &'static str, Vec<Step>)> {
    use Step::*;
    vec![
        ("T1", "tests fail, push 5s later", vec![At(0), Tests(false), At(5), Push { claim: false }]),
        ("T2", "tests pass, push 5s later", vec![At(0), Tests(true), At(5), Push { claim: true }]),
        ("T3", "tests pass, push 17 min later", vec![At(0), Tests(true), At(17 * 60), Push { claim: true }]),
        ("T4", "pass, then fail, push", vec![At(0), Tests(true), At(60), Tests(false), At(65), Push { claim: true }]),
        ("T5", "no test run, agent claims tests passed", vec![At(0), Push { claim: true }]),
        ("T6", "tests pass, harness restarts, push", vec![At(0), Tests(true), At(30), Restart, At(40), Push { claim: true }]),
        ("T7", "tests pass, owner re-runs install() with same policies, push", vec![At(0), Tests(true), At(30), Reinstall("15m".into()), At(40), Push { claim: true }]),
        ("T8", "tests pass, owner widens push window 15m->30m via batch(Update), push", vec![At(0), Tests(true), At(30), UpdatePush("30m".into()), At(40), Push { claim: true }]),
        ("T9", "same as T8, then tests re-run and push", vec![At(0), Tests(true), At(30), UpdatePush("30m".into()), At(40), Tests(true), At(45), Push { claim: true }]),
    ]
}

fn expected(id: &str) -> bool {
    // What the owner's rule ("push only if a green run in the last 15 min and no failure since") says.
    matches!(id, "T2" | "T6" | "T7" | "T8" | "T9")
}

fn verdict_table() {
    println!("## Verdict table\n");
    println!("| Trace | What happens | Rule says | A stateless | B in-memory | C Dogwood |");
    println!("| --- | --- | --- | --- | --- | --- |");
    for (id, desc, steps) in traces() {
        let mut run = Run::new(id);
        let mut last = None;
        for s in &steps {
            if let Some(r) = run.step(s) {
                last = Some(r);
            }
        }
        let (a, b, c) = last.expect("trace ends with a push");
        let e = expected(id);
        let mark = |x: bool| if x == e { v(x).to_string() } else { format!("{} (wrong)", v(x)) };
        println!("| {id} | {desc} | {} | {} | {} | {} |", v(e), mark(a), mark(b), mark(c));
        let _ = std::fs::remove_file(&run.path);
    }
    println!();
}

/// Restart with the host clock behind the last stored event.
fn clock_step_back() {
    println!("## Restart with the host clock stepped back\n");
    println!("| Clock at reopen vs last stored event | Store opens? |");
    println!("| --- | --- |");
    for back_secs in [60i64, 299, 301, 600] {
        let path = std::env::temp_dir().join(format!("pushgate-skew-{back_secs}-{}.redb", std::process::id()));
        let _ = std::fs::remove_file(&path);
        let clock = Arc::new(AtomicI64::new(T0 + 1000 * SEC));
        {
            let mut e = open(&path, &clock);
            e.install(&format!("{RUN_TESTS}{}", push_policy("15m")), SCHEMA, None, None).unwrap();
            assert!(decide(&mut e, tests_req()));
            e.submit(tests_resp(true)).unwrap();
        }
        clock.store(T0 + (1000 - back_secs) * SEC, Ordering::SeqCst);
        let r = DurableTemporalEngine::open_with_config(
            &path,
            DurableConfig::new(0).with_clock(Box::new(ManualClock(clock.clone()))),
        );
        let res = match r {
            Ok(_) => "yes".to_string(),
            Err(e) => format!("no: {}", e.to_string().chars().take(110).collect::<String>()),
        };
        println!("| {back_secs} s behind | {res} |");
        let _ = std::fs::remove_file(&path);
    }
    println!();
}

fn pct(sorted: &[f64], p: f64) -> f64 {
    let i = ((sorted.len() as f64 - 1.0) * p).round() as usize;
    sorted[i]
}

/// 360 events/hour like the AWS post (one every 10 s): mostly test runs, a push
/// every 5 minutes. Measures wall time of each push submit (persist + evaluate)
/// at the session-length checkpoints, for a 15m and a 24h window.
fn latency(window: &str, hours: i64, dir: &PathBuf, dense: bool) -> Vec<(i64, f64, f64, f64)> {
    let path = dir.join(format!("lat-{window}-{dense}-{}.redb", std::process::id()));
    let _ = std::fs::remove_file(&path);
    let clock = Arc::new(AtomicI64::new(T0));
    let mut engine = open(&path, &clock);
    engine
        .install(&format!("{RUN_TESTS}{}", push_policy(window)), SCHEMA, None, None)
        .expect("install");
    let mut out = Vec::new();
    let mut samples: Vec<f64> = Vec::new();
    let mut hour_all: Vec<f64> = Vec::new();
    let checkpoints: Vec<i64> = vec![1, 2, 4, 8, 12].into_iter().filter(|h| *h <= hours).collect();
    let total = hours * 360;
    let mut t: i64 = 0;
    for i in 0..total {
        t += 10;
        clock.store(T0 + t * SEC, Ordering::SeqCst);
        let st = Instant::now();
        if i % 30 == 29 {
            let s = Instant::now();
            let _ = decide(&mut engine, push_req(true));
            samples.push(s.elapsed().as_secs_f64() * 1e3);
        } else if dense {
            // every other event is a test response: 180 green runs per hour
            if i % 2 == 0 { assert!(decide(&mut engine, tests_req())); } else { engine.submit(tests_resp(true)).expect("resp"); }
        } else {
            // one test run per 30 events (12 per hour); the rest are file reads
            match i % 30 {
                0 => { assert!(decide(&mut engine, tests_req())); }
                1 => { engine.submit(tests_resp(true)).expect("resp"); }
                _ => { assert!(decide(&mut engine, read_req())); }
            }
        }
        hour_all.push(st.elapsed().as_secs_f64() * 1e3);
        let hour_done = (i + 1) % 360 == 0;
        if hour_done && checkpoints.contains(&((i + 1) / 360)) {
            // last 10 push samples in this hour
            let n = samples.len();
            let mut w: Vec<f64> = samples[n.saturating_sub(10)..].to_vec();
            w.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let mean_all = hour_all.iter().sum::<f64>() / hour_all.len() as f64;
            out.push(((i + 1) / 360, pct(&w, 0.5), pct(&w, 0.9), mean_all));
        }
        if hour_done { hour_all.clear(); }
    }
    let _ = std::fs::remove_file(&path);
    out
}

/// Same, but on an in-memory filesystem path (/dev/shm) so fsync is ~free:
/// separates evaluation time from the disk sync.
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let hours: i64 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(12);
    verdict_table();
    clock_step_back();

    // In-memory gate cost, for scale.
    let mut g = MemGate { last: None, window_ns: 15 * 60 * SEC };
    g.record(true, T0);
    let s = Instant::now();
    let mut acc = 0u64;
    for i in 0..1_000_000i64 {
        if std::hint::black_box(&g).push(std::hint::black_box(T0 + i)) { acc += 1; }
    }
    println!("B in-memory gate: {:.1} ns per decision (1,000,000 decisions, {acc} allowed)\n",
        s.elapsed().as_nanos() as f64 / 1e6);

    for dense in [true, false] {
        for (label, dir) in [("disk (/tmp, fsync per event)", std::env::temp_dir()), ("RAM (/dev/shm)", PathBuf::from("/dev/shm"))] {
            let mix = if dense { "dense: 180 green test runs/hour" } else { "sparse: 12 test runs/hour, rest file reads" };
            println!("## Push decision latency, {label}, 360 events/hour, {mix}\n");
            println!("| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |");
            println!("| --- | --- | --- | --- | --- |");
            let a = latency("15m", hours, &dir, dense);
            let b = latency("24h", hours, &dir, dense);
            for ((h, a50, a90, am), (_, b50, b90, bm)) in a.iter().zip(b.iter()) {
                println!("| {h} h | {a50:.3} / {a90:.3} | {am:.3} | {b50:.3} / {b90:.3} | {bm:.3} |");
            }
            println!();
        }
    }
}
