//! Does injecting a memory vector actually change what the model writes — and
//! does it still write anything at all?
//!
//! Both halves matter and the second is not rhetorical. The norm-matching
//! investigation recorded in `blend_inject_matched` found that a raw additive
//! blend collapsed the output to empty tokens at *every* alpha, because the
//! encode output routinely has 15-20x the residual's own norm. So the first
//! thing to establish is that generation survives; "the output changed" is
//! worthless if what it changed into is degenerate.
//!
//! This deliberately does not try to judge whether the injection helped. That
//! question needs memory-dependent prompts and a real A/B, which lives on the
//! Swift side where the memory store is. This answers the prior question:
//! does the mechanism function.
//!
//! Usage:  test_inject_generate <model.jgen>

use jcross_engine_glm::{jcross_engine_reset, InjectionSpec, JCrossEngine};

/// `execute_generation_loop` does not clear the KV cache — the contract is that
/// the caller resets before each independent generation, which
/// `JCrossChatManager.generate` and `PipelineRunner` both do.
///
/// Worth stating because omitting it here is what the first run of this test
/// did, and the result was thoroughly misleading: every injected run appeared
/// to differ from the baseline, including at alpha=0 where the blend is a
/// no-op. The difference was the previous run's positions still sitting in the
/// cache, not the injection. Without the alpha=0 control that would have read
/// as "injection works".
fn reset(engine: &JCrossEngine) {
    jcross_engine_reset(engine as *const JCrossEngine as *mut std::os::raw::c_void);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: test_inject_generate <model.jgen>");
        std::process::exit(2);
    }
    let engine = JCrossEngine::load_jgen(&args[1]).expect("load");
    let n = engine.num_layers;
    let hidden = engine.hidden_dim().expect("hidden_dim");
    println!("model: {} layers, hidden {}\n", n, hidden);

    // Low, definitely-in-vocab ids: this is about the mechanism, not the text.
    let prompt: Vec<u32> = (0..10u32).map(|i| 100 + i).collect();
    let max = 16;

    reset(&engine);
    let baseline = engine
        .execute_generation_loop(&prompt, max, None, std::ptr::null_mut())
        .expect("baseline");
    println!("baseline           : {:?}", baseline);

    // A real memory-shaped vector: an actual encode of a token sequence, which
    // is exactly what EternalMemoryStore stores.
    reset(&engine);
    let memory = engine.execute_worker_forward(&[500, 501, 502, 503]).expect("encode");
    let mnorm: f32 = memory.iter().map(|v| v * v).sum::<f32>().sqrt();
    println!("memory vector      : dim {}, L2 norm {:.1}", memory.len(), mnorm);

    let mut failures = 0;
    let mut check = |ok: bool, label: &str| {
        println!("{} {}", if ok { "  ok  " } else { " FAIL " }, label);
        if !ok { failures += 1; }
    };

    // ── Route B: mid-layer residual, swept for the usable band ─────────────
    //
    // The first version of this asserted that generation survives at *every*
    // alpha, which is simply not a reasonable expectation: alpha is a mix
    // ratio, so alpha=1 means "replace the residual with the memory direction"
    // and destroying the output is the correct behaviour, not a bug. The
    // useful question is where the usable band ends, because that is what sets
    // the default. So this measures rather than demands.
    println!("\n-- layer injection (route B), sweeping strength --");
    let mut last_healthy = 0.0f32;
    for &alpha in &[0.1f32, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0] {
        let spec = InjectionSpec {
            layer_injections: vec![(n / 3, memory.clone(), alpha)],
            ..Default::default()
        };
        reset(&engine);
        let out = engine
            .execute_generation_loop_injected(&prompt, max, None, std::ptr::null_mut(), Some(&spec))
            .expect("injected generate");
        let distinct = {
            let mut v = out.clone();
            v.sort_unstable();
            v.dedup();
            v.len()
        };
        // Healthy = ran to the requested length without the cycle detector
        // cutting in, and did not degenerate into a couple of repeating ids.
        let healthy = out.len() == max && distinct >= max / 2;
        if healthy { last_healthy = alpha; }
        println!("  alpha={:<4} {:<9} {} distinct/{} -> {:?}",
                 alpha, if healthy { "healthy" } else { "DEGRADED" }, distinct, out.len(), out);
    }
    println!("  highest healthy strength: {}", last_healthy);
    check(last_healthy > 0.0,
          &format!("there is a usable strength band (up to alpha={})", last_healthy));

    // At alpha 0 the blend is a no-op, so anything other than the baseline
    // means the injection path itself perturbs the forward pass.
    let zero = InjectionSpec {
        layer_injections: vec![(n / 3, memory.clone(), 0.0)],
        ..Default::default()
    };
    reset(&engine);
    let zero_out = engine
        .execute_generation_loop_injected(&prompt, max, None, std::ptr::null_mut(), Some(&zero))
        .expect("alpha 0");
    check(zero_out == baseline,
          "alpha=0 reproduces the baseline exactly (the path itself is neutral)");

    // And it must actually do something at a real strength, or the whole
    // feature is a no-op that happens to compile.
    let strong = InjectionSpec {
        layer_injections: vec![(n / 3, memory.clone(), 0.6)],
        ..Default::default()
    };
    reset(&engine);
    let strong_out = engine
        .execute_generation_loop_injected(&prompt, max, None, std::ptr::null_mut(), Some(&strong))
        .expect("alpha 0.6");
    check(strong_out != baseline, "alpha=0.6 changes the output");

    // ── Route A: soft prefix ───────────────────────────────────────────────
    println!("\n-- soft prefix (route A) --");
    // Embedding-space rows, which is what this slot expects — taking real token
    // embeddings rather than feeding the final-layer memory vector, whose
    // distribution does not belong here.
    let soft: Vec<Vec<f32>> = vec![
        engine.embedding_row(700).expect("embed row"),
        engine.embedding_row(701).expect("embed row"),
    ];
    let spec_soft = InjectionSpec { soft: soft.clone(), ..Default::default() };
    reset(&engine);
    let soft_out = engine
        .execute_generation_loop_injected(&prompt, max, None, std::ptr::null_mut(), Some(&spec_soft))
        .expect("soft generate");
    println!("  2 soft rows -> {:?}", soft_out);
    check(soft_out != baseline, "soft prefix changes the output");
    // Not asserted: these are embedding rows for two arbitrary token ids with
    // no relation to the prompt, so a degraded continuation is a plausible and
    // uninteresting outcome. Whether *meaningful* soft rows help is the A/B
    // question, not this one.
    println!("  (soft-prefix quality is not asserted here — arbitrary rows, see comment)");

    // Both routes at once, since they are independent by construction.
    let both = InjectionSpec {
        soft,
        layer_injections: vec![(n / 3, memory.clone(), 0.3)],
        ..Default::default()
    };
    reset(&engine);
    let both_out = engine
        .execute_generation_loop_injected(&prompt, max, None, std::ptr::null_mut(), Some(&both))
        .expect("both");
    check(!both_out.is_empty(), "both routes together produce output");

    println!("\n=== {} ===", if failures == 0 { "ALL OK" } else { "FAILURES" });
    if failures != 0 { std::process::exit(1); }
}
