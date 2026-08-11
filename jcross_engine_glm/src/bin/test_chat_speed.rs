//! Real-prompt generation + marginal decode speed for one JGEN.
//!
//! Usage: test_chat_speed <model.jgen> [prompt] [n_tokens]
//! Loads the model's own tokenizer sidecar, applies the Qwen chat template,
//! prints the decoded reply and the tokens/sec measured on decode only
//! (prefill and the first token's weight upload are timed separately, so a
//! slow load cannot masquerade as a slow model).

use jcross_engine_glm::JCrossEngine;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: test_chat_speed <model.jgen> [prompt] [n]");
        std::process::exit(2);
    }
    let prompt_text = args.get(2).cloned()
        .unwrap_or_else(|| "日本の首都はどこですか?".to_string());
    let n: usize = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(48);

    let tok_path = format!("{}.tokenizer/tokenizer.json", args[1]);
    let tokenizer = tokenizers::Tokenizer::from_file(&tok_path)
        .expect("tokenizer sidecar");
    let templated = format!(
        "<|im_start|>user\n{}<|im_end|>\n<|im_start|>assistant\n", prompt_text);
    let enc = tokenizer.encode(templated, false).expect("encode");
    let prompt: Vec<u32> = enc.get_ids().to_vec();
    eprintln!("prompt: {} tokens", prompt.len());

    let t_load = Instant::now();
    let eng = JCrossEngine::load_jgen(&args[1]).expect("load");
    eprintln!("load: {:.1}s", t_load.elapsed().as_secs_f64());

    // First token separately: it pays every lazy weight build/upload.
    let t_first = Instant::now();
    let first = eng.execute_generation_loop(&prompt, 1, None, std::ptr::null_mut())
        .expect("first token");
    eprintln!("prefill+first token (weights upload included): {:.1}s",
              t_first.elapsed().as_secs_f64());

    let t_dec = Instant::now();
    let toks = eng.execute_generation_loop(&prompt, n, None, std::ptr::null_mut())
        .expect("generation");
    let dt = t_dec.elapsed().as_secs_f64();

    let text = tokenizer.decode(&toks, true).unwrap_or_default();
    println!("--- reply ({} tokens) ---", toks.len());
    println!("{}", text);
    println!("--- decode speed: {:.2} tok/s (run 2, weights warm) ---",
             toks.len() as f64 / dt);
    let _ = first;
}
