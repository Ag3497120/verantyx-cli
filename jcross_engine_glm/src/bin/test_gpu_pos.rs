//! Checks that the GPU encode path advances its absolute sequence position
//! across calls.
//!
//! `encode_gpu_batched` used to recover `start_pos` from `gpu_kv[0]`'s row
//! count. That is wrong for any model whose layer 0 does not write a KV cache --
//! and layer 0 of a Qwen3.5/3.6 hybrid is `linear_attention`, which runs on CPU
//! and never touches `gpu_kv`. The slot stayed `None` forever, so every call
//! after the first silently restarted at position 0 and re-applied RoPE from the
//! beginning. No error, no crash: just wrong numbers.
//!
//! The position assertion is what actually catches this. That was established by
//! running the old derivation back in on purpose: it reported `3` then `3`
//! instead of `3` then `6`.
//!
//! The hidden-state comparison below is deliberately NOT the discriminator, and
//! the same experiment is why. Under the bug the two encodes still produced
//! *different* hidden states -- the full-attention layers' KV caches do
//! accumulate across calls, so the second batch really does attend to the first;
//! only its RoPE positions are wrong. So "the output changed" is satisfied by
//! both the correct and the broken engine, and treating it as proof would be a
//! test that always passes. It is kept as a weak liveness check and labelled as
//! such.
//!
//! Usage:  JCROSS_HYBRID_GPU=1 test_gpu_pos <model.jgen>

use jcross_engine_glm::JCrossEngine;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: test_gpu_pos <model.jgen>");
        std::process::exit(2);
    }
    let engine = JCrossEngine::load_jgen(&args[1]).expect("load");

    println!("gpu_pos at start : {}", engine.gpu_pos.get());
    assert_eq!(engine.gpu_pos.get(), 0, "fresh engine must start at 0");

    let a = engine.encode_gpu_batched(&[], &[101, 102, 103]).expect("encode 1");
    let after_first = engine.gpu_pos.get();
    println!("after 3 tokens   : {}", after_first);

    let b = engine.encode_gpu_batched(&[], &[101, 102, 103]).expect("encode 2");
    let after_second = engine.gpu_pos.get();
    println!("after 3 more     : {}", after_second);

    let mut failed = false;

    if after_first != 3 || after_second != 6 {
        println!("FAIL: expected 3 then 6, got {} then {}", after_first, after_second);
        failed = true;
    }

    // Weak liveness only -- see the module comment. This differs under the bug
    // too, so it proves the engine ran, not that position advanced.
    let identical = a.len() == b.len()
        && a.iter().zip(b.iter()).all(|(x, y)| x.to_bits() == y.to_bits());
    if identical {
        println!("FAIL: two encodes produced a byte-identical hidden state -- the \
                  second call did not see the first at all");
        failed = true;
    } else {
        let worst = a.iter().zip(b.iter()).map(|(x, y)| (x - y).abs()).fold(0.0f32, f32::max);
        println!("hidden differs   : worst|delta|={:e}  (liveness only, not the check)", worst);
    }

    // reset must return to 0, or the next turn resumes into a cache that is gone.
    jcross_engine_glm::jcross_engine_reset(
        &engine as *const JCrossEngine as *mut std::os::raw::c_void
    );
    println!("after reset      : {}", engine.gpu_pos.get());
    if engine.gpu_pos.get() != 0 {
        println!("FAIL: reset did not zero gpu_pos");
        failed = true;
    }

    println!();
    if failed { std::process::exit(1); }
    println!("PASS: gpu_pos advances across calls and resets to 0");
}
