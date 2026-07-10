import os
import sys
import argparse
import subprocess
import json

def fetch_model(repo_id):
    print(f"[*] Vera Bridge: Fetching model {repo_id} from HuggingFace...")
    try:
        # Use huggingface-cli to download the model
        result = subprocess.run([
            "huggingface-cli", "download", repo_id,
            "--exclude", "*.bin", "*.h5", "*.msgpack" # Prefer safetensors
        ], capture_output=True, text=True, check=True)
        
        # The last line of stdout is usually the cache directory path
        lines = result.stdout.strip().split('\n')
        cache_dir = lines[-1] if lines else ""
        print(f"[+] Model downloaded successfully to: {cache_dir}")
        print(cache_dir) # Output the path so Swift can read it
    except subprocess.CalledProcessError as e:
        print(f"[-] Fetch failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def encode_prompt(repo_id, prompt):
    try:
        from transformers import AutoTokenizer
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        tokenizer = AutoTokenizer.from_pretrained(repo_id)
        tokens = tokenizer.encode(prompt)
        print(json.dumps(tokens))
    except Exception as e:
        print(f"[-] Encode failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

def decode_tokens(repo_id, token_ids_str):
    try:
        from transformers import AutoTokenizer
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        tokenizer = AutoTokenizer.from_pretrained(repo_id)
        token_ids = json.loads(token_ids_str)
        text = tokenizer.decode(token_ids, skip_special_tokens=True)
        print(text)
    except Exception as e:
        print(f"[-] Decode failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Vera Python Bridge (HF & Tokenizer)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_fetch = subparsers.add_parser("fetch")
    parser_fetch.add_argument("repo", type=str)
    
    parser_encode = subparsers.add_parser("encode")
    parser_encode.add_argument("repo", type=str)
    parser_encode.add_argument("prompt", type=str)
    
    parser_decode = subparsers.add_parser("decode")
    parser_decode.add_argument("repo", type=str)
    parser_decode.add_argument("tokens", type=str)
    
    args = parser.parse_args()
    
    if args.command == "fetch":
        fetch_model(args.repo)
    elif args.command == "encode":
        encode_prompt(args.repo, args.prompt)
    elif args.command == "decode":
        decode_tokens(args.repo, args.tokens)

if __name__ == "__main__":
    main()
