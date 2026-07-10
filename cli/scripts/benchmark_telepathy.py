import sys
import subprocess
import time
import requests
import json
import re

# ==============================================================================
# Verantyx God-Mode vs Base Model Benchmark
# ==============================================================================

# Standard Logic / Constraints Puzzles
PUZZLES = [
    {
        "id": "1_apples_oranges",
        "prompt": "Box A contains 3 apples and 2 mandarin oranges. Take one apple from Box A and place it into Box B. Then eat one mandarin orange from Box B. Finally, return the remaining apple from Box B to Box A. How many apples and oranges are in Box A and Box B now?"
    },
    {
        "id": "2_murder_mystery",
        "prompt": "Alice, Bob, and Charlie are in a room. Alice leaves the room. Then Bob puts a key in his pocket. Charlie watches Bob. Alice returns. Who knows where the key is?"
    },
    {
        "id": "3_temporal_stacking",
        "prompt": "Place the red block on the blue block. Then place the green block on the red block. Finally, remove the red block. Which block is on top of the blue block now?"
    },
    {
        "id": "4_math_reasoning",
        "prompt": "A store sells shirts for $10 and pants for $20. If I buy 2 shirts and 1 pair of pants, and use a $5 discount coupon, how much do I pay in total?"
    }
]

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:0.5b" # Using base 0.5B model in Ollama for fair comparison

def run_base_model(prompt):
    """Runs the prompt through the base autoregressive model via Ollama."""
    print(f"    -> Running Base Model ({OLLAMA_MODEL}) via Ollama...")
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }
    try:
        start_time = time.time()
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        duration = time.time() - start_time
        result = response.json().get("response", "").strip()
        return result, duration
    except Exception as e:
        return f"[Error connecting to Ollama: {e}]", 0.0

def run_swarm_model(prompt):
    """Runs the prompt through the Verantyx God-Mode Swarm."""
    print(f"    -> Running Telepathic Swarm...")
    try:
        start_time = time.time()
        process = subprocess.Popen(
            ["python3", "cli/scripts/bucket_relay_swarm_experimental.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=prompt.encode('utf-8'))
        duration = time.time() - start_time
        
        output = stdout.decode('utf-8', errors='ignore')
        # Strip ANSI escape codes
        output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
        
        # Parse final output from Coder
        match = re.search(r"=== CODER \(QWEN 0\.5B JGEN\) OUTPUT ===\n(.*?)\n========================================", output, re.DOTALL)
        if match:
            # Clean up warnings
            result = match.group(1).strip()
            # Remove huggingface warnings if any
            result = re.sub(r"/usr/local/lib/.*?warnings\.warn\(", "", result, flags=re.DOTALL).strip()
            return result, duration
        else:
            return "[Failed to parse Swarm output]", duration
            
    except Exception as e:
        return f"[Error running Swarm: {e}]", 0.0

def main():
    print("==================================================")
    print("Verantyx Telepathic Swarm Benchmark")
    print(f"Base Model: {OLLAMA_MODEL} vs Swarm (qwen_0.5b_full.jgen)")
    print("==================================================\n")
    
    # Pre-pull the ollama model if not exists
    print(f"Ensuring Ollama model '{OLLAMA_MODEL}' is pulled...")
    try:
        requests.post("http://localhost:11434/api/pull", json={"name": OLLAMA_MODEL}, stream=False)
    except:
        print("Warning: Could not connect to Ollama. Make sure 'ollama serve' is running.")
    
    markdown_report = f"# Verantyx Telepathic Swarm Benchmark Results\n\n"
    markdown_report += f"**Base Model**: {OLLAMA_MODEL} (Autoregressive Token Generation)\n"
    markdown_report += f"**Verantyx Swarm**: 3-Agent Qwen 0.5B Swarm (1024D Pure Vector Communication + Cascading Lock)\n\n"
    
    for i, puzzle in enumerate(PUZZLES):
        print(f"Testing Puzzle {i+1}/{len(PUZZLES)}: {puzzle['id']}")
        
        base_ans, base_time = run_base_model(puzzle["prompt"])
        swarm_ans, swarm_time = run_swarm_model(puzzle["prompt"])
        
        # Format report
        markdown_report += f"## Puzzle {i+1}: {puzzle['id']}\n"
        markdown_report += f"> {puzzle['prompt']}\n\n"
        
        markdown_report += f"### ❌ Base Model ({OLLAMA_MODEL})\n"
        markdown_report += f"*{base_time:.2f}s*\n"
        markdown_report += f"```text\n{base_ans}\n```\n\n"
        
        markdown_report += f"### ✅ Verantyx God-Mode Swarm\n"
        markdown_report += f"*{swarm_time:.2f}s*\n"
        markdown_report += f"```text\n{swarm_ans}\n```\n\n"
        
        markdown_report += "---\n\n"
        
        print(f"    [Done] Base: {base_time:.1f}s | Swarm: {swarm_time:.1f}s\n")
        
    # Write report
    report_path = "/Users/motonishikoudai/.gemini/antigravity/brain/1bd52a68-dd24-44c8-b5c4-ac42db53d23d/benchmark_results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown_report)
        
    print(f"Benchmark complete! Results saved to {report_path}")

if __name__ == "__main__":
    main()
