//! Proves that splitting a model's layers across two engine instances produces
//! bitwise-identical results to running the whole stack in one.
//!
//! This is the load-bearing test for pipeline-parallel inference. Everything
//! else in that feature -- the wire protocol, pairing, transfer, the UI -- is
//! plumbing around the assumption verified here: that
//!
//!     engineA.segment(tokens, 0..k)  ->  h
//!     engineB.segment(h,      k..N)  ->  result
//!
//! equals
//!
//!     engine.segment(tokens, 0..N)   ->  result
//!
//! down to the last bit. Two separate `JCrossEngine` instances are used
//! deliberately, not one engine called twice: each mmaps the file and owns its
//! own KV cache and (for hybrids) its own GDN recurrent state, which is exactly
//! the situation two machines are in. Calling one engine twice would share both
//! caches and could pass while the real split fails.
//!
//! Bitwise rather than approximate, because both sides run the identical CPU
//! kernels in the identical order -- there is no reordering that would justify
//! a tolerance. Any drift at all means state is leaking across the boundary.
//!
//! Usage:  test_layer_split <model.jgen> [split_layer] [num_tokens]

use jcross_engine_glm::{
    JCrossEngine, SegmentInput, SegmentOutput, SEG_FLAG_FINAL_NORM, SEG_FLAG_LM_HEAD_ARGMAX,
};

fn hidden_rows(out: SegmentOutput) -> ndarray::Array2<f32> {
    match out {
        SegmentOutput::Hidden(a) => a,
        SegmentOutput::Token(t) => panic!("expected hidden state, got token {}", t),
    }
}

fn token_of(out: SegmentOutput) -> u32 {
    match out {
        SegmentOutput::Token(t) => t,
        SegmentOutput::Hidden(_) => panic!("expected token, got hidden state"),
    }
}

/// Returns (mismatched_count, worst_abs_delta).
fn compare(a: &ndarray::Array2<f32>, b: &ndarray::Array2<f32>) -> (usize, f32) {
    assert_eq!(a.shape(), b.shape(), "shape mismatch: {:?} vs {:?}", a.shape(), b.shape());
    let mut mismatched = 0usize;
    let mut worst = 0.0f32;
    for (x, y) in a.iter().zip(b.iter()) {
        if x.to_bits() != y.to_bits() {
            mismatched += 1;
            let d = (x - y).abs();
            if d > worst { worst = d; }
        }
    }
    (mismatched, worst)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: test_layer_split <model.jgen> [split_layer] [num_tokens]");
        std::process::exit(2);
    }
    let path = &args[1];
    let n_tokens: usize = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(8);

    // Two independent instances, as two machines would be.
    let whole = JCrossEngine::load_jgen(path).expect("load whole");
    let head = JCrossEngine::load_jgen(path).expect("load head");
    let tail = JCrossEngine::load_jgen(path).expect("load tail");

    let n = whole.num_layers;
    let k: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(n / 2);
    assert!(k >= 1 && k < n, "split layer {} must be in 1..{}", k, n);

    // Low, definitely-in-vocab ids: this test is about layer arithmetic, not
    // about any particular text.
    let tokens: Vec<u32> = (0..n_tokens as u32).map(|i| 100 + i).collect();

    println!("model      : {}", path);
    println!("num_layers : {}", n);
    println!("split at   : {}  -> head [0,{}) / tail [{},{})", k, k, k, n);
    println!("tokens     : {}", n_tokens);
    println!();

    // --- Prefill: whole stack, one instance -------------------------------
    let whole_out = whole
        .execute_layer_segment(SegmentInput::Tokens(&tokens), 0, n, 0, SEG_FLAG_FINAL_NORM)
        .expect("whole prefill");
    let whole_h = hidden_rows(whole_out);

    // --- Prefill: split across two instances ------------------------------
    let mid = hidden_rows(
        head.execute_layer_segment(SegmentInput::Tokens(&tokens), 0, k, 0, 0)
            .expect("head prefill"),
    );
    let split_h = hidden_rows(
        tail.execute_layer_segment(SegmentInput::Hidden(mid), k, n, 0, SEG_FLAG_FINAL_NORM)
            .expect("tail prefill"),
    );

    let (bad, worst) = compare(&whole_h, &split_h);
    println!(
        "prefill  [{} x {}]  mismatched={}  worst|delta|={:e}",
        whole_h.nrows(), whole_h.ncols(), bad, worst
    );
    let mut failed = bad != 0;

    // --- Decode: one more step, exercising KV reuse on both sides ---------
    // The prefill above populated whole/head/tail KV caches at positions
    // 0..n_tokens. A decode step at start_pos = n_tokens is where a split that
    // mishandles position or cache ownership diverges, so it is worth its own
    // assertion rather than trusting prefill alone.
    let next = [200u32];
    let whole_tok = token_of(
        whole
            .execute_layer_segment(
                SegmentInput::Tokens(&next), 0, n, n_tokens, SEG_FLAG_LM_HEAD_ARGMAX,
            )
            .expect("whole decode"),
    );
    let mid2 = hidden_rows(
        head.execute_layer_segment(SegmentInput::Tokens(&next), 0, k, n_tokens, 0)
            .expect("head decode"),
    );
    let split_tok = token_of(
        tail.execute_layer_segment(
            SegmentInput::Hidden(mid2), k, n, n_tokens, SEG_FLAG_LM_HEAD_ARGMAX,
        )
        .expect("tail decode"),
    );

    println!("decode   whole_token={}  split_token={}", whole_tok, split_tok);
    if whole_tok != split_tok {
        failed = true;
    }

    println!();
    if failed {
        println!("FAIL: split does not reproduce the whole stack");
        std::process::exit(1);
    }
    println!("PASS: split is bitwise identical to the whole stack");
}
