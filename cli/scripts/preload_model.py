import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='[Preload] %(message)s')

MODEL_ID = "Qwen/Qwen1.5-0.5B"

def main():
    logger = logging.getLogger("preload")
    logger.info(f"Checking and pre-downloading model: {MODEL_ID}")
    
    # Download or load from cache
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True
        )
        logger.info("Model is ready in cache.")
    except Exception as e:
        logger.error(f"Failed to preload model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
