/* jcross_engine.h — C ABI for jcross_engine_glm (Swift / ctypes bridge)
 *
 * Mirror of the extern "C" exports in src/lib.rs and the ctypes.argtypes
 * declarations in verantyx_mind.py (RustBrain). Keep param order in sync.
 *
 * Build: cargo build --release [--no-default-features]
 * Library: libjcross_engine_glm.dylib (macOS) / .so (Linux) / .dll (Windows)
 */
#ifndef JCROSS_ENGINE_H
#define JCROSS_ENGINE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void *jcross_engine_create(const char *path);
void jcross_engine_destroy(void *engine);
void jcross_engine_reset(void *engine);
void jcross_engine_trim(void *engine);

int32_t jcross_engine_hidden_dim(void *engine);
int32_t jcross_engine_num_layers(void *engine);

int32_t jcross_engine_generate(
    void *engine,
    const uint32_t *prompt, size_t prompt_len,
    size_t max_tokens,
    uint32_t *out, size_t out_len);

int32_t jcross_engine_encode(
    void *engine,
    const uint32_t *tokens, size_t tokens_len,
    float *out, size_t out_len);

int32_t jcross_engine_encode_soft(
    void *engine,
    const float *soft, size_t n_soft, size_t soft_dim,
    const uint32_t *tokens, size_t tokens_len,
    float *out, size_t out_len);

int32_t jcross_engine_encode_layers(
    void *engine,
    const uint32_t *tokens, size_t tokens_len,
    const uint32_t *layers, size_t n_layers,
    float *out, size_t out_len);

int32_t jcross_engine_inject_at_layer(
    void *engine,
    const uint32_t *tokens, size_t tokens_len,
    uint32_t inject_layer,
    const float *inject, size_t inject_len,
    float alpha,
    float *out, size_t out_len);

int32_t jcross_engine_puzzle_inference(
    void *engine,
    const char *layer_name,
    const float *input, size_t input_len,
    uint32_t *out_token,
    float *out_entropy);

/* Softmax top-K over lm_head. Returns N pairs written, or negative on error. */
int32_t jcross_engine_topk_distribution(
    void *engine,
    const char *layer_name,
    const float *input, size_t input_len,
    size_t k,
    uint32_t *out_token_ids,
    float *out_probs);

/* Copy embed_tokens[token_id] into out (length = hidden_dim). */
int32_t jcross_engine_embedding_row(
    void *engine,
    uint32_t token_id,
    float *out, size_t out_len);

int32_t jcross_engine_project(
    void *engine,
    const char *layer_name,
    const float *input, size_t input_len,
    float *out, size_t out_len);

int32_t jcross_engine_resynthesize(
    void *engine,
    const char *layer_name,
    const float *input, size_t input_len,
    float *out, size_t out_len);

int32_t jcross_engine_optimize_thought_in_place(
    void *engine,
    const char *layer_name,
    float *input, size_t input_len,
    size_t max_steps,
    float lr,
    float temperature,
    float *out_entropy);

#ifdef __cplusplus
}
#endif

#endif /* JCROSS_ENGINE_H */
