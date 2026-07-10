"""
chat_qwen_rust.py — JCross Qwen Interactive REPL
-----------------------------------------------------
思考と発話の分離設計:
  Phase 1 (Think): モデルに <think> ... </think> ブロックを自由に生成させる（内部思考）
  Phase 2 (Speak): Think の出力を context に含めたうえで、最終応答を生成（発話）

使い方:
  python3 -u chat_qwen_rust.py
  python3 -u chat_qwen_rust.py --think-tokens 80 --speak-tokens 120
"""

import ctypes
import os
import sys
import time
import argparse

# ── CLI 引数 ────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="JCross Qwen Interactive REPL")
parser.add_argument("--model", default="/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen", help="Path to .jgen model")
parser.add_argument("--tokenizer", default="Qwen/Qwen1.5-0.5B-Chat", help="HuggingFace tokenizer name")
parser.add_argument("--think-tokens", type=int, default=60, help="Max tokens for internal thinking phase")
parser.add_argument("--speak-tokens", type=int, default=80, help="Max tokens for final response phase")
parser.add_argument("--no-think", action="store_true", help="Skip thinking phase (direct generation)")
args = parser.parse_args()

# ── ライブラリ読み込み ────────────────────────────────────────────────────────────
DYLIB = "/Users/motonishikoudai/verantyx-cli/jcross_engine_glm/target/release/libjcross_engine_glm.dylib"
if not os.path.exists(DYLIB):
    print(f"[ERROR] Library not found: {DYLIB}")
    print("  → Run: cargo build --lib --release in jcross_engine_glm/")
    sys.exit(1)

lib = ctypes.CDLL(DYLIB)
lib.jcross_engine_create.argtypes  = [ctypes.c_char_p]
lib.jcross_engine_create.restype   = ctypes.c_void_p
lib.jcross_engine_generate.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_size_t,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_size_t,
]
lib.jcross_engine_generate.restype = ctypes.c_int
lib.jcross_engine_destroy.argtypes  = [ctypes.c_void_p]
lib.jcross_engine_destroy.restype   = None

lib.jcross_engine_reset.argtypes = [ctypes.c_void_p]
lib.jcross_engine_reset.restype = None

# ── エンジン初期化 ────────────────────────────────────────────────────────────────
print(f"\n╔══════════════════════════════════════════╗")
print(f"║   JCross Local Inference REPL            ║")
print(f"╚══════════════════════════════════════════╝")
print(f"Model : {args.model}")
print(f"Think : {'OFF (direct)' if args.no_think else str(args.think_tokens) + ' tokens'}")
print(f"Speak : {args.speak_tokens} tokens")
print()

engine = lib.jcross_engine_create(args.model.encode("utf-8"))
if not engine:
    print("[ERROR] Failed to initialize JCrossEngine. Check model path.")
    sys.exit(1)
print("[OK] Engine loaded.\n")

# ── トークナイザー ────────────────────────────────────────────────────────────────
try:
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    print(f"[OK] Tokenizer loaded: {args.tokenizer}\n")
except Exception as e:
    print(f"[ERROR] Tokenizer load failed: {e}")
    lib.jcross_engine_destroy(engine)
    sys.exit(1)

# ── Helper: run_generate ─────────────────────────────────────────────────────────
def run_generate(prompt_text: str, max_tokens: int, label: str = "GEN") -> list[int]:
    """プロンプトテキストをトークン化し、Rust エンジンで生成。生成トークンIDリストを返す。"""
    tokens = tokenizer.encode(prompt_text, add_special_tokens=False)
    prompt_len = len(tokens)
    prompt_arr = (ctypes.c_uint32 * prompt_len)(*tokens)
    out_len = prompt_len + max_tokens + 16
    out_arr = (ctypes.c_uint32 * out_len)()

    # KVキャッシュをリセット（Think/Speak フェーズ間・ターン間で汚染を防ぐ）
    lib.jcross_engine_reset(engine)
    t0 = time.time()
    result_len = lib.jcross_engine_generate(engine, prompt_arr, prompt_len, max_tokens, out_arr, out_len)
    elapsed = time.time() - t0

    if result_len < 0:
        print(f"  [{label}] Engine error: {result_len}")
        return []

    generated = [out_arr[i] for i in range(result_len)]
    print(f"  [{label}] Raw token IDs: {generated}")
    tps = result_len / elapsed if elapsed > 0 else 0
    print(f"  [{label}] {result_len} tokens in {elapsed:.2f}s ({tps:.2f} tok/s)")
    return generated


# ── インタラクティブ REPL ─────────────────────────────────────────────────────────
SYSTEM = "You are a helpful assistant."

print("─" * 46)
print("  Interactive mode. Type 'exit' or Ctrl+C to quit.")
print("─" * 46)

while True:
    # ── ユーザー入力受付 ──────────────────────────────────────────────────────────
    try:
        user_input = input("\n🧑 You: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[Exiting]")
        break

    if not user_input or user_input.lower() in ("exit", "quit", "q"):
        print("[Exiting]")
        break

    # ────────────────────────────────────────────────────────────────────────────
    # Phase 1: Think（思考フェーズ）
    #   モデルに <think>...</think> 形式の内部推論を生成させる
    # ────────────────────────────────────────────────────────────────────────────
    thought_text = ""
    if not args.no_think:
        think_prompt = (
            f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
            f"<|im_start|>user\n{user_input}<|im_end|>\n"
            f"<|im_start|>think\n"   # ← 思考ブロックの開始タグ
        )
        print("\n  [思考フェーズ]", end="", flush=True)
        think_ids = run_generate(think_prompt, args.think_tokens, label="THINK")

        if think_ids:
            thought_text = tokenizer.decode(think_ids, skip_special_tokens=True)
            # </think> より前の部分だけを抽出（もしモデルが閉じた場合）
            if "</think>" in thought_text:
                thought_text = thought_text.split("</think>")[0].strip()
            print(f"\n  💭 Thought: {thought_text[:200]}{'...' if len(thought_text) > 200 else ''}")

    # ────────────────────────────────────────────────────────────────────────────
    # Phase 2: Speak（発話フェーズ）
    #   思考結果を context に注入し、最終応答を生成する
    # ────────────────────────────────────────────────────────────────────────────
    if thought_text:
        # 思考を hidden context として system に挿入する設計
        speak_prompt = (
            f"<|im_start|>system\n{SYSTEM}\n"
            f"[Internal reasoning: {thought_text}]<|im_end|>\n"
            f"<|im_start|>user\n{user_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    else:
        speak_prompt = (
            f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
            f"<|im_start|>user\n{user_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

    print("\n  [発話フェーズ]", end="", flush=True)
    speak_ids = run_generate(speak_prompt, args.speak_tokens, label="SPEAK")

    if speak_ids:
        response = tokenizer.decode(speak_ids, skip_special_tokens=True)
        # 不要なシステム/思考ブロックのエコーが含まれていれば除去
        if "[Internal reasoning:" in response:
            response = response.split("]")[-1].strip()
        print(f"\n🤖 Assistant: {response}\n")
    else:
        print("\n[No response generated]\n")


# ── 終了処理 ──────────────────────────────────────────────────────────────────────
lib.jcross_engine_destroy(engine)
print("[Engine destroyed cleanly.]")
