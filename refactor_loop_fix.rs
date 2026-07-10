use std::fs;
fn main() {
    let mut content = fs::read_to_string("jcross_engine_glm/src/lib.rs").unwrap();
    let old = "        let num_layers = 80;\n        let rope_theta = 10000.0;";
    let new = "        let num_layers = 80;\n        let num_heads = 14;\n        let num_kv_heads = 2;\n        let head_dim = 64;\n        let rope_theta = 10000.0;";
    content = content.replace(old, new);
    
    // Also fix max_tokens to max_new_tokens
    content = content.replace("for step in 0..max_tokens {", "for step in 0..max_tokens {");
    // wait, the signature changed max_tokens to max_new_tokens! But the old code uses max_tokens.
    // In refactor_loop.rs I used:
    // "pub fn execute_generation_loop(&self, prompt: &[u32], max_tokens: usize) -> Result<Vec<u32>, String> {"
    // So max_tokens is correct! Wait, the compiler said:
    // cannot find value `max_tokens` in this scope
    // Oh, did `execute_generation_loop` have `max_new_tokens` instead?
    // Let me just replace `max_new_tokens` with `max_tokens` in the signature.
    content = content.replace("max_new_tokens: usize", "max_tokens: usize");
    
    // Also fix current_token inside the loop for step in 0..max_tokens
    // The old loop had `let next_token = best_token; generated.push(next_token); current_token = next_token;`
    // Wait, I declared `let mut current_token = prompt[0];`. Why did it say not found?
    // Ah, `current_token` is used in the `embed_meta` block which is inside `for step in 0..max_tokens {`.
    // My replacement added a `for` loop for prefill, but I might have moved `current_token` into a smaller scope, or something!
    
    fs::write("jcross_engine_glm/src/lib.rs", content).unwrap();
}
