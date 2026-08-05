//! Does the hybrid Metal path produce the same generation as the CPU path?
//!
//! `JCROSS_HYBRID_GPU` is opt-in with a comment saying the Metal path stays
//! that way "until GDN-on-device is stable". Deciding whether to flip it needs
//! evidence, and the evidence so far is one sample: a single mission on
//! ornith-1.0-9b where CPU wrote 53 tokens opening an `<analysis>` block and
//! Metal wrote 7 tokens echoing the instruction. That is suggestive and not
//! more than that — one prompt, one run.
//!
//! The framing matters. This is not "which device writes better text": CPU is
//! the reference implementation, and Metal's job is to agree with it. So the
//! measurement is divergence *between* the two, plus a repetition score for
//! each, across several prompts:
//!
//!   divergence ~0     Metal reproduces CPU — the path is sound
//!   divergence high, both coherent
//!                     Metal computes something different but well-formed;
//!                     still a defect, since the same weights and the same
//!                     greedy sampling should give the same tokens
//!   GPU distinct2 well below CPU's
//!                     Metal is degrading the output — the failure the single
//!                     sample hinted at
//!
//! Greedy sampling throughout, so any difference is arithmetic, not chance.
//!
//! Usage:  test_hybrid_device_ab <model.jgen> [max_tokens]

use jcross_engine_glm::gen_quality::measure;
use jcross_engine_glm::{jcross_engine_reset, JCrossEngine};

fn reset(engine: &JCrossEngine) {
    jcross_engine_reset(engine as *const JCrossEngine as *mut std::os::raw::c_void);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: test_hybrid_device_ab <model.jgen> [max_tokens]");
        std::process::exit(2);
    }
    let max: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(32);

    // Metal must be available at all, or this compares CPU with CPU and reports
    // a flawless match — the same shape of false pass that a stale KV cache
    // produced earlier in this work.
    std::env::set_var("JCROSS_GPU", "1");
    std::env::set_var("JCROSS_HYBRID_GPU", "1");

    let engine = JCrossEngine::load_jgen(&args[1]).expect("load");
    println!("model      : {}", args[1]);
    println!("layers     : {}, hidden {}", engine.num_layers,
             engine.hidden_dim().unwrap_or(0));
    println!("hybrid     : {}", if engine.hybrid.is_some() { "yes" } else { "NO — this test is meaningless for a non-hybrid model" });
    println!("max tokens : {}\n", max);

    let prompts: Vec<Vec<u32>> = vec![
        (0..12u32).map(|i| 100 + i).collect(),
        (0..12u32).map(|i| 900 + i).collect(),
        (0..12u32).map(|i| 2000 + i * 3).collect(),
        (0..12u32).map(|i| 5000 + i * 7).collect(),
    ];

    println!("{:<7} {:>10} {:>10} {:>11} {:>11} {}",
             "prompt", "cpu tokens", "gpu tokens", "cpu dist2", "gpu dist2", "divergence");

    let mut divergences = Vec::new();
    let mut cpu_d2 = Vec::new();
    let mut gpu_d2 = Vec::new();

    for (i, p) in prompts.iter().enumerate() {
        std::env::set_var("JCROSS_HYBRID_GPU", "0");
        reset(&engine);
        let cpu = engine
            .execute_generation_loop(p, max, None, std::ptr::null_mut())
            .expect("cpu");

        std::env::set_var("JCROSS_HYBRID_GPU", "1");
        reset(&engine);
        let gpu = engine
            .execute_generation_loop(p, max, None, std::ptr::null_mut())
            .expect("gpu");

        // CPU is the reference, so quality is measured against itself (giving
        // divergence 0) and Metal against CPU.
        let qc = measure(&cpu, &cpu);
        let qg = measure(&gpu, &cpu);

        println!("{:<7} {:>10} {:>10} {:>11.2} {:>11.2} {:>10.2}",
                 i, cpu.len(), gpu.len(), qc.distinct2, qg.distinct2, qg.divergence);

        divergences.push(qg.divergence);
        cpu_d2.push(qc.distinct2);
        gpu_d2.push(qg.distinct2);
    }

    let mean = |v: &[f32]| v.iter().sum::<f32>() / v.len().max(1) as f32;
    let md = mean(&divergences);
    let mc = mean(&cpu_d2);
    let mg = mean(&gpu_d2);

    println!("\nmean divergence (Metal vs CPU) : {:.3}", md);
    println!("mean distinct2  cpu {:.2}  gpu {:.2}", mc, mg);
    println!();

    // Thresholds stated rather than tuned to make the answer come out a
    // particular way. Identical weights and greedy sampling should give
    // identical tokens; anything else is the interesting result.
    if md < 0.02 {
        println!("=> Metal reproduces CPU. The hybrid GPU path looks sound on this model.");
    } else if mg < mc * 0.8 {
        println!("=> Metal DEGRADES the output: repetition is materially worse than CPU's \
                  ({:.2} vs {:.2}), and it diverges by {:.2}. Keep JCROSS_HYBRID_GPU opt-in.", mg, mc, md);
    } else {
        println!("=> Metal diverges from CPU by {:.2} while staying about as well-formed.", md);
        println!("   Same weights, same greedy sampling — so this is an arithmetic difference, \
                  not a style difference, and it is a defect even though the text reads fine.");
        println!("   Keep JCROSS_HYBRID_GPU opt-in until it is found.");
    }
}
