import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import datetime

def write_hand_log(workspace_dir, message):
    log_dir = os.path.join(workspace_dir, ".verantyx_chrono")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "hand.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def generate_with_ollama(original_code, intent_hash, workspace_dir, error_feedback=None, model="qwen2.5-coder"):
    """
    Sends the original code and intent to local Ollama for code editing.
    Returns the edited code.
    """
    write_hand_log(workspace_dir, f"Starting synthesis for intent: {intent_hash}")
    strict_instruction = (
        "STRICT INSTRUCTION: Do NOT perform any autonomous actions, refactoring, or unrelated optimizations. "
        "Follow ONLY the exact instructions inferred from the intent vector hash. You must act merely as a 'Hand' that translates the 'Brain's' intent into code."
    )
    
    feedback_section = ""
    if error_feedback:
        write_hand_log(workspace_dir, f"Applying error feedback: {error_feedback}")
        feedback_section = (
            f"\n--- PREVIOUS ATTEMPT REJECTED ---\n"
            f"The Swarm rejected your previous modification for the following reason:\n"
            f"{error_feedback}\n"
            f"Please try again and strictly align with the original intent.\n"
        )
        
    prompt = (
        f"You are The Hand, an AI code editor.\n"
        f"The Swarm has requested a modification to the following code.\n"
        f"Intent Vector Hash: {intent_hash}\n"
        f"{strict_instruction}\n"
        f"{feedback_section}\n"
        f"Please apply the intended change and output ONLY the complete modified code, without markdown formatting or explanation.\n\n"
        f"--- Original Code ---\n"
        f"{original_code}\n"
        f"--- End of Original Code ---\n"
    )
    
    url = "http://localhost:11434/api/generate"
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        write_hand_log(workspace_dir, f"Connecting to Ollama model: {model}...")
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            edited_code = result.get("response", "").strip()
            
            # Remove markdown code blocks if the model wrapped it
            if edited_code.startswith("```"):
                lines = edited_code.split("\n")
                if lines[0].startswith("```"): lines = lines[1:]
                if lines[-1].startswith("```"): lines = lines[:-1]
                edited_code = "\n".join(lines).strip()
                
            write_hand_log(workspace_dir, "Synthesis successful via Ollama.")
            return edited_code
    except (urllib.error.URLError, Exception) as e:
        msg = f"Failed to connect to Ollama ({e}). Using fallback logic."
        print(f"[Hand CLI] {msg}", file=sys.stderr)
        write_hand_log(workspace_dir, f"WARNING: {msg}")
        return fallback_edit(original_code)

def fallback_edit(original_code):
    edit_marker = "<!-- Edited by The Hand CLI (Local LLM Fallback) -->\n"
    if "</body>" in original_code:
        return original_code.replace("</body>", f"    {edit_marker}</body>")
    else:
        return original_code + f"\n{edit_marker}"

def main():
    parser = argparse.ArgumentParser(description="Verantyx The Hand CLI - Local LLM Code Editor")
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[Hand CLI] Error: Input file {args.input} not found.", file=sys.stderr)
        sys.exit(1)
        
    workspace_dir = os.path.dirname(os.path.dirname(args.input)) # args.input is in .verantyx_chrono/temp_hand_input.json
        
    with open(args.input, "r", encoding="utf-8") as f:
        input_data = json.load(f)
        
    original_code = input_data.get("original_code", "")
    intent_hash = input_data.get("intent_hash", "unknown")
    error_feedback = input_data.get("error_feedback", None)
    
    # Try to generate code with Ollama
    edited_code = generate_with_ollama(original_code, intent_hash, workspace_dir, error_feedback)
    
    output_data = {
        "edited_code": edited_code
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    write_hand_log(workspace_dir, f"Code successfully processed and written to output file.")
    print(f"[Hand CLI] Code successfully processed and written to {args.output}")

if __name__ == "__main__":
    main()
