//! A/B: f16 JGEN vs requantized JGEN on the same prompt.
//!
//! Usage: test_quant_ab <f16.jgen> <quant.jgen> [n_tokens]
//!
//! Greedy decode on both, same prompt tokens, then report agreement. Perfect
//! token identity is NOT the pass bar — q4_k rounds — but early divergence
//! (first few tokens) or garbage means the block plumbing is wrong, which is
//! what this exists to catch before anyone waits on a 50 GB requant.

use jcross_engine_glm::JCrossEngine;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: test_quant_ab <f16.jgen> <quant.jgen> [n_tokens]");
        std::process::exit(2);
    }
    let n: usize = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(24);
    // Neutral prompt tokens; small ids exist in every vocab.
    let prompt: Vec<u32> = vec![151644, 872, 198, 108386, 151645, 198, 151644, 77091, 198];

    let a = JCrossEngine::load_jgen(&args[1]).expect("load f16");
    let t0 = Instant::now();
    let ta = a.execute_generation_loop(&prompt, n, None, std::ptr::null_mut())
        .expect("f16 generation");
    let da = t0.elapsed();
    drop(a);

    let b = JCrossEngine::load_jgen(&args[2]).expect("load quant");
    let t1 = Instant::now();
    let tb = b.execute_generation_loop(&prompt, n, None, std::ptr::null_mut())
        .expect("quant generation");
    let db = t1.elapsed();

    let agree = ta.iter().zip(tb.iter()).take_while(|(x, y)| x == y).count();
    println!("f16   ({:5.1}s, {:4.1} tok/s): {:?}", da.as_secs_f64(),
             ta.len() as f64 / da.as_secs_f64(), &ta);
    println!("quant ({:5.1}s, {:4.1} tok/s): {:?}", db.as_secs_f64(),
             tb.len() as f64 / db.as_secs_f64(), &tb);
    println!("prefix agreement: {}/{}", agree, ta.len().min(tb.len()));
    if agree == 0 && !ta.is_empty() {
        eprintln!("FIRST TOKEN DIVERGES — plumbing suspect, do not requant the big model");
        std::process::exit(1);
    }
}
