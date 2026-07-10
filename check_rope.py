import torch
def test():
    try:
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained("THUDM/glm-4-9b-chat", trust_remote_code=True, device_map="cpu", low_cpu_mem_usage=True)
        print("Model loaded")
    except Exception as e:
        print("No GLM-4", e)
