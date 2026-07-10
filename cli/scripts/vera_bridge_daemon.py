import os
import sys
import json
import struct
import subprocess
import time

# We don't need torch or numpy anymore for inference!
from transformers import AutoTokenizer

MODEL_ID = "Qwen/Qwen3.6-27B"
SNAPSHOT_DIR = os.path.expanduser(f"~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")

print("[*] Initializing Vera Python Bridge Daemon...")

# 1. Load Tokenizer
print("[*] Loading Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

# 2. Extract Safetensor Offsets
print("[*] Extracting Head and Embeddings safetensor offsets...")
index_path = os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json")
with open(index_path, "r") as f:
    weight_map = json.load(f)["weight_map"]

def get_tensor_info(safetensors_path, target_substrings):
    with open(safetensors_path, 'rb') as f:
        header_size = struct.unpack('<Q', f.read(8))[0]
        header_json = f.read(header_size).decode('utf-8')
        header = json.loads(header_json)
        for key in header:
            if any(sub in key for sub in target_substrings):
                start, end = header[key]['data_offsets']
                absolute_start = 8 + header_size + start
                return absolute_start, end - start
    return None, None

embed_file = weight_map.get("model.embed_tokens.weight") or weight_map.get("model.language_model.embed_tokens.weight")
embed_path = os.path.join(SNAPSHOT_DIR, embed_file)
embed_offset, embed_size = get_tensor_info(embed_path, ["embed_tokens.weight"])

lm_head_file = weight_map.get("lm_head.weight")
lm_head_path = os.path.join(SNAPSHOT_DIR, lm_head_file)
lm_head_offset, lm_head_size = get_tensor_info(lm_head_path, ["lm_head.weight"])

norm_file = weight_map.get("model.language_model.norm.weight") or weight_map.get("model.norm.weight")
norm_path = os.path.join(SNAPSHOT_DIR, norm_file)
norm_offset, norm_size = get_tensor_info(norm_path, ["model.language_model.norm.weight", "model.norm.weight"])

print(f"  > embed_tokens file: {embed_file}, offset: {embed_offset}, size: {embed_size}")
print(f"  > lm_head file: {lm_head_file}, offset: {lm_head_offset}, size: {lm_head_size}")
print(f"  > final_norm file: {norm_file}, offset: {norm_offset}, size: {norm_size}")

# 3. Spawn Swift Zero-Copy Daemon
print("[*] Spawning Verantyx JCross Daemon...")
cli_path = os.path.abspath("./.build/arm64-apple-macosx/release/verantyx-cli")
jcross_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../qwen_27b.jcross"))

daemon_args = [
    cli_path, "daemon", jcross_path, "-v",
    "--embed-path", embed_path,
    "--embed-offset", str(embed_offset),
    "--embed-size", str(embed_size),
    "--lm-head-path", lm_head_path,
    "--lm-head-offset", str(lm_head_offset),
    "--lm-head-size", str(lm_head_size),
    "--norm-path", norm_path,
    "--norm-offset", str(norm_offset),
    "--norm-size", str(norm_size)
]

process = subprocess.Popen(
    daemon_args,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=sys.stderr
)

print("[*] Waiting for READY signal from Daemon...")
ready = process.stdout.read(6)
print(f"[*] Received signal: {ready}")
if ready != b"READY\n":
    print("[-] Daemon failed to start properly. Exiting.")
    sys.exit(1)

def generate_text(prompt, max_tokens=50):
    print(f"\n[Prompt]: {prompt}\n")
    print("[AI]: ", end="", flush=True)
    
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": prompt}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text)
    current_token = None
    
    # Send all prompt tokens sequentially to build context
    for i, token_id in enumerate(input_ids):
        # We only need the output of the LAST token to predict the next
        is_last = (i == len(input_ids) - 1)
        
        # Send 4-byte Token ID (UInt32)
        vec = struct.pack('<I', token_id)
        try:
            process.stdin.write(vec)
            process.stdin.flush()
        except BrokenPipeError:
            print("[-] BrokenPipeError: Swift daemon crashed.")
            break
        
        # Swift will ALWAYS return 4 bytes now!
        expected_bytes = 4
        
        out_bytes = b""
        while len(out_bytes) < expected_bytes:
            chunk = process.stdout.read(expected_bytes - len(out_bytes))
            if not chunk: break
            out_bytes += chunk
            
        if len(out_bytes) < expected_bytes:
            print("[-] Incomplete read. Swift probably crashed.")
            break
        
        next_token = struct.unpack("<I", out_bytes)[0]
        token_str = tokenizer.decode([next_token])
        print(f"\n[Prompt Token {i}] Sent: {token_id}, Received: {next_token} ({repr(token_str)})")
        if is_last:
            current_token = next_token
    
    start_time = time.time()
    generated_tokens = 0
    # Auto-Regressive Loop
    for _ in range(max_tokens):
        if current_token == tokenizer.eos_token_id:
            break
            
        vec = struct.pack('<I', current_token)
        process.stdin.write(vec)
        process.stdin.flush()
        
        out_bytes = b""
        while len(out_bytes) < 4:
            chunk = process.stdout.read(4 - len(out_bytes))
            if not chunk: break
            out_bytes += chunk
            
        if len(out_bytes) < 4:
            break
            
        next_token = struct.unpack("<I", out_bytes)[0]
        token_str = tokenizer.decode([next_token])
        print(f"[{next_token}:{repr(token_str)}]", end="", flush=True)
        
        current_token = next_token
        generated_tokens += 1
        
    end_time = time.time()
    print(f"\n\n[+] Generation Complete. Generated {generated_tokens} tokens in {end_time - start_time:.2f} seconds ({generated_tokens / (end_time - start_time):.2f} tokens/s).")

if __name__ == "__main__":
    import sys
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Explain quantum physics."
    max_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    generate_text(prompt, max_tokens)
    
    # Close daemon
    process.stdin.close()
    process.wait()
