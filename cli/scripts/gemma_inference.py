import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from gemma_trainer import load_gemma_jgen

def run_inference(prompt, max_new_tokens=50):
    print(f"--- Prompt ---\n{prompt}\n--------------")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Target device: {device}")
    model_id = "google/gemma-4-12B"
    
    # 1. Load the dense model into CPU first (Do NOT use MPS yet, to prevent 24GB VRAM explosion)
    print("Loading Gemma 12B Meta Model to CPU...")
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    
    # 2. Inject the true JCross generative base (replaces dense linear layers with lightweight JCross layers)
    jgen_path = "/Users/motonishikoudai/verantyx-cli/cli/gemma_12b_generative.jgen"
    print(f"Injecting Base JGEN from {jgen_path}...")
    load_gemma_jgen(model, jgen_path, device="cpu") # Inject on CPU first
    
    # 3. Force Garbage Collection to discard the old 24GB dense weights
    import gc
    gc.collect()
    
    # 4. Now move the slimmed 4GB skeleton to the Mac's GPU (MPS)
    print(f"Transferring the optimized JCross skeleton to {device}...")
    model = model.to(device)
    if device == "mps":
        torch.mps.empty_cache()
    
    # We skip muscle injection to test the pure JGEN generation
    # muscle_path = "gemma_12b_muscles_step_900.pt"
    # print(f"Injecting Muscle Memory from {muscle_path}...")
    # muscles = torch.load(muscle_path, map_location=device)
    # for name, param in model.named_parameters():
    #     if param.requires_grad and name in muscles:
    #         param.data.copy_(muscles[name].to(device))
    
    model.eval()
    
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    print("Generating response...")
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7)
        
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"\n[Gemma 12B Healed Output]\n{result}")

if __name__ == "__main__":
    test_prompt = "1969年にアポロ11号に乗って、人類で初めて月面に降り立った宇宙飛行士の名前をフルネームで答えてください。"
    run_inference(test_prompt)
    
    print("\n" + "="*50 + "\n")
    
    code_prompt = """def hello_world():
    print("Hello, Verantyx!")
"""
    run_inference(code_prompt, max_new_tokens=30)
