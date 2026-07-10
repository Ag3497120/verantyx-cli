import gradio as gr
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
import os
import time

print("Loading CPU & Cartridge System...")
model_id = "Qwen/Qwen1.5-0.5B-Chat"
device = "mps" if torch.backends.mps.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cpu")

# --- CPU Surgery (Adding the Cartridge Slot) ---
class GenerativeLinear(nn.Module):
    def __init__(self, original_linear):
        super().__init__()
        self.weight = nn.Parameter(original_linear.weight.clone(), requires_grad=False)
        if original_linear.bias is not None:
            self.bias = nn.Parameter(original_linear.bias.clone(), requires_grad=False)
        else:
            self.register_parameter('bias', None)
        
        # The Cartridge Slot
        self.mod_memory = None 

    def forward(self, x):
        h = torch.matmul(x, self.weight.T)
        if self.bias is not None:
            h = h + self.bias
            
        if self.mod_memory is not None:
            # Inject Latent Knowledge Cartridge
            h = h + self.mod_memory
            
        return h

def inject_surgery(m):
    for name, module in m.named_modules():
        if isinstance(module, nn.Linear) and "mlp" in name:
            parent_name = name.rsplit('.', 1)[0]
            child_name = name.rsplit('.', 1)[1]
            parent = m.get_submodule(parent_name)
            setattr(parent, child_name, GenerativeLinear(module))

inject_surgery(model)
model.to(device)
model.eval()

target_layer = model.model.layers[12].mlp.down_proj

# --- Load Cartridges ---
cartridges = {
    "Vanilla (知識なし)": None,
}

if os.path.exists("cartridges/legal.pt"):
    cartridges["Legal (法律特化)"] = torch.load("cartridges/legal.pt").to(device) * 5.0
if os.path.exists("cartridges/medical.pt"):
    cartridges["Medical (医療特化)"] = torch.load("cartridges/medical.pt").to(device) * 5.0
if os.path.exists("cartridges/oss.pt"):
    cartridges["OSS Code (プログラミング)"] = torch.load("cartridges/oss.pt").to(device) * 5.0

def chat_infer(message, history, cartridge_name):
    # 1. Swap Cartridge
    target_layer.mod_memory = cartridges.get(cartridge_name, None)
    
    # 2. Prepare Prompt
    messages = [{"role": "user", "content": message}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # 3. Generate
    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            inputs["input_ids"],
            max_new_tokens=100,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id
        )
    latency = time.time() - start_time
    
    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    
    # Telemetry string
    telemetry = f"🧠 CPU: Qwen-0.5B\n"
    telemetry += f"📝 Prompt Context: {inputs['input_ids'].shape[1]} Tokens (No Hidden Text)\n"
    telemetry += f"💿 Cartridge: {cartridge_name}\n"
    telemetry += f"⚡ Latency: {latency:.2f}s"
    
    return response, telemetry

# --- Gradio UI ---
with gr.Blocks(title="Verantyx: The Cartridge AI") as demo:
    gr.Markdown("# 🧠 Verantyx: The Cartridge AI Paradigm")
    gr.Markdown("LLMは知識を持たない「ただのCPU」になりました。右上のドロップダウンから**知識カートリッジ（JCross潜在ベクトル）**を挿し替えるだけで、プロンプトにテキストを追加することなく、全く異なる特化型AIへと瞬時に変貌します。")
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=400)
            msg = gr.Textbox(label="Prompt", placeholder="例: 『詳しく教えてください』とだけ入力してください。")
            submit = gr.Button("Submit")
        
        with gr.Column(scale=1):
            cartridge_dropdown = gr.Dropdown(
                choices=list(cartridges.keys()), 
                value="Vanilla (知識なし)", 
                label="💿 Knowledge Cartridge Slot"
            )
            telemetry_box = gr.Textbox(label="Telemetry (Proof of No RAG)", lines=5, interactive=False)
            
    def respond(message, chat_history, cartridge_name):
        bot_message, telemetry = chat_infer(message, chat_history, cartridge_name)
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": bot_message})
        return "", chat_history, telemetry
        
    submit.click(respond, [msg, chatbot, cartridge_dropdown], [msg, chatbot, telemetry_box])
    msg.submit(respond, [msg, chatbot, cartridge_dropdown], [msg, chatbot, telemetry_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
