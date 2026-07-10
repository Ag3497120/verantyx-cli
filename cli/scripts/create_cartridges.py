import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import os

model_id = "Qwen/Qwen1.5-0.5B-Chat"
device = "mps" if torch.backends.mps.is_available() else "cpu"

print("Loading Base Model for Cartridge Extraction...")
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cpu")
model.to(device)
model.eval()

# We extract from Layer 12
target_layer = model.model.layers[12].mlp.down_proj

def extract_cartridge(text, filename):
    print(f"\nExtracting Cartridge: {filename}...")
    inputs = tokenizer(text, return_tensors="pt").to(device)
    
    captured_memory = None
    def capture_hook(module, input, output):
        nonlocal captured_memory
        # Mean pool across sequence to get the "Concept Vector"
        captured_memory = output.mean(dim=1, keepdim=True).clone().detach()
        
    hook = target_layer.register_forward_hook(capture_hook)
    
    with torch.no_grad():
        model(inputs["input_ids"])
        
    hook.remove()
    
    # Save the extracted vector as a cartridge
    os.makedirs("cartridges", exist_ok=True)
    torch.save(captured_memory.cpu(), f"cartridges/{filename}")
    print(f"Saved {filename}! Shape: {captured_memory.shape}")

# 1. Legal Cartridge
legal_text = """
The Supreme Court ruling establishes a precedent regarding intellectual property rights in the digital age.
Under Article 10 of the Copyright Act, fair use exemptions apply strictly to educational and non-commercial transformations.
Penalty for infringement includes statutory damages up to $150,000 per violation.
"""
extract_cartridge(legal_text, "legal.pt")

# 2. Medical Cartridge
medical_text = """
The patient presents with severe tachycardia and elevated troponin levels indicating an acute myocardial infarction.
Immediate administration of sublingual nitroglycerin and intravenous heparin is required.
Prepare for emergency cardiac catheterization and percutaneous coronary intervention.
"""
extract_cartridge(medical_text, "medical.pt")

# 3. Code / OSS Cartridge
oss_text = """
pub fn compile_ast(node: &ASTNode) -> Result<String, Error> {
    match node {
        ASTNode::FunctionDef(name, args, body) => {
            let compiled_body = compile_block(body)?;
            Ok(format!("fn {}({}) {{\n{}\n}}", name, args.join(", "), compiled_body))
        }
    }
}
"""
extract_cartridge(oss_text, "oss.pt")

print("\n✅ All Cartridges generated successfully!")
