import sys
import torch
import gc

# Add current dir to path to import shell and swarm modules
import os
sys.path.append(os.path.dirname(__file__))

import bucket_relay_swarm
from verantyx_shell import CommanderLanguageInterface

class TranslatorAgent:
    def __init__(self, model_id="Qwen/Qwen1.5-0.5B-Chat"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  [\033[35mTranslator\033[0m] Loading lightweight {model_id} for Natural Language Generation...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float16, device_map="auto")
        
    def translate(self, concept_string):
        print(f"  [\033[35mTranslator\033[0m] Synthesizing fluent response from concepts...")
        messages = [
            {"role": "system", "content": (
                "You are Verantyx, an advanced and highly intelligent AI assistant. "
                "You will receive a list of fragmented concept keywords (some may be non-sense or multi-lingual). "
                "Your strict task is to interpret the hidden meaning behind these concepts and generate a SINGLE, natural, fluent, and polite Japanese conversational response. "
                "CRITICAL INSTRUCTION: DO NOT just list, quote, or enumerate the keywords. You must synthesize a coherent Japanese sentence that sounds like a human speaking."
            )},
            {"role": "user", "content": f"Concept Fragments: {concept_string}\n\nGenerate a natural Japanese conversational response."}
        ]
        
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            generated_ids = self.model.generate(
                model_inputs.input_ids,
                max_new_tokens=100,
                temperature=0.7
            )
            
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response.strip()

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_pipeline.py \"Your message here\"")
        return

    user_input = sys.argv[1]
    print(f"\n[\033[36mSYSTEM\033[0m] Initiating Verantyx Flow with Dynamic Cognitive Anchors...\n")
    print(f"User Input: {user_input}")
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    worker_jgen = "/Users/motonishikoudai/verantyx-cli/cli/gemma_12b_generative.jgen"
    scout_jgen = "/Users/motonishikoudai/verantyx-cli/cli/commander_12b_rank1024.jgen"
    memory_file = "/Users/motonishikoudai/verantyx-cli/my_clone.memory"
    
    memory_bank = bucket_relay_swarm.TelepathicMemoryBank(memory_file)
    hidden_dim = 3840
    
    commander_interface = CommanderLanguageInterface(target_dim=hidden_dim, device=device)
    
    # 1. Generate Linguistic Cognitive Anchor
    print(f"  [\033[33mCommander\033[0m] Establishing Linguistic Cognitive Anchor (Natural Japanese)...")
    anchor_texts = [
        "私はあなたを理解し、明確に説明します。",
        "これは論理的な結論であり、自然な会話です。",
        "人間が使う標準的で丁寧な言葉遣いです。"
    ]
    anchor_vectors = [commander_interface.encode(t) for t in anchor_texts]
    linguistic_anchor = torch.mean(torch.stack(anchor_vectors), dim=0)
    
    # 2. Commander Encoding & Logging
    print(f"  [\033[33mCommander\033[0m] Translating natural language to intent vector...")
    intent_vector = commander_interface.encode(user_input)
    
    print(f"  [\033[33mCommander\033[0m] Generating Meta-Instruction (Translate to concepts)...")
    translation_instruction_text = "Translate the underlying pure thought into a coherent, fluent Japanese sentence."
    translation_instruction_vector = commander_interface.encode(translation_instruction_text)
    
    # [NEW] Log Commander Encoding Behaviors
    memory_bank.add_memory(intent_vector, label="Commander Intent Log")
    memory_bank.add_memory(translation_instruction_vector, label="Commander Meta-Instruction Log")
    
    # Retrieve past contexts
    current_thought = memory_bank.retrieve_memory(intent_vector)
    
    # --- LINGUISTIC ADAPTER SETUP ---
    import torch.nn as nn
    import torch.optim as optim
    import os
    import time
    
    adapter_path = "/Users/motonishikoudai/verantyx-cli/linguistic_adapter.pt"
    adapter = nn.Linear(hidden_dim, hidden_dim, bias=False).to(device)
    if os.path.exists(adapter_path):
        adapter.load_state_dict(torch.load(adapter_path, map_location=device))
        print(f"  [\033[32mAdapter\033[0m] Linguistic Adapter loaded from {adapter_path}")
    else:
        # Initialize as Identity matrix so it does nothing initially
        nn.init.eye_(adapter.weight)
        print(f"  [\033[33mAdapter\033[0m] Initialized new Linguistic Adapter (Identity).")
        
    optimizer = optim.Adam(adapter.parameters(), lr=0.01)
    
    # 3. DYNAMIC THINKING & ONLINE HEALING LOOP
    max_depth = 50  # Let it learn for up to 50 iterations
    threshold = 0.40 # Target similarity
    current_depth = 0
    
    print(f"\n  [\033[35mDynamic Loop\033[0m] Starting Adaptive Computation & Online Healing (Target: {threshold})...")
    
    total_start_time = time.time()
    
    # Base thought generated from worker and scout once, then we adapter-tune it.
    print(f"\n  [\033[36mBase Inference\033[0m] Processing Swarm Topology...")
    try:
        worker_brain = bucket_relay_swarm.JCrossBrain(worker_jgen, device)
        base_thought = worker_brain.forward_latent(current_thought, role_name="Worker", color_code=bucket_relay_swarm.C_WORKER)
        del worker_brain
        bucket_relay_swarm.purge_memory()
        
        scout_brain = bucket_relay_swarm.JCrossBrain(scout_jgen, device)
        base_thought = scout_brain.forward_latent(base_thought, role_name="Scout", color_code=bucket_relay_swarm.C_SCOUT)
        del scout_brain
        bucket_relay_swarm.purge_memory()
    except Exception as e:
        print(f"Brain Error: {e}")
        base_thought = current_thought

    # Detach base thought to act as input to adapter
    base_thought = base_thought.detach().requires_grad_(False)
    
    while current_depth < max_depth:
        step_start_time = time.time()
        current_depth += 1
        
        optimizer.zero_grad()
        
        # Apply the Linguistic Adapter (Meta-Translation mapping)
        adapted_thought = adapter(base_thought)
        
        # Calculate Loss against Linguistic Anchor
        loss = 1.0 - torch.nn.functional.cosine_similarity(adapted_thought, linguistic_anchor).mean()
        similarity = 1.0 - loss.item()
        
        step_end_time = time.time()
        step_duration = step_end_time - step_start_time
        print(f"    [\033[35mCognitive Check Depth {current_depth}\033[0m] Anchor Similarity: {similarity:.5f} (Target: {threshold}) - Loss: {loss.item():.5f}")
        
        if similarity >= threshold:
            print(f"    [\033[32mThreshold Reached\033[0m] The Linguistic Adapter successfully shifted the vector to natural language space at Depth {current_depth}!")
            break
        else:
            if current_depth < max_depth:
                # Online Healing (Backpropagation)
                print(f"    [\033[33mHealing\033[0m] Updating Adapter Weights to learn translation mapping...")
                loss.backward()
                optimizer.step()
            else:
                print(f"    [\033[31mMax Depth Reached\033[0m] Stopping adaptive computation.")

    # Save the learned experience
    torch.save(adapter.state_dict(), adapter_path)
    print(f"  [\033[32mMemory\033[0m] Linguistic Adapter (Experience) safely saved to SSD.")

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    print(f"\n  [\033[34mTime Report\033[0m] Total Time for Healing Loop: {total_duration:.2f} seconds.")

    # 4. DECODING (Pure LM_Head extraction, No Qwen)
    print(f"\n  [\033[33mCommander\033[0m] Decoding final conceptual state directly via LM_Head...")
    # Add translation instruction context to final extraction if needed, or decode directly
    final_thought = adapted_thought.detach()
    concept_cloud = commander_interface.decode(final_thought)
    
    print(f"\n" + "="*60)
    print(f"[\033[35mVerantyx Direct Output\033[0m] {concept_cloud}")
    print("="*60 + "\n")
    print(f"[\033[32mSUCCESS\033[0m] Task processed. Encoding logs & thoughts stored to {memory_file}\n")

if __name__ == "__main__":
    main()
