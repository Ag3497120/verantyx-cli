import os
with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    content = f.read()

new_synth = """
        # We MUST take the entire sequence, otherwise the Coder loses all context of the thought!
        current_sequence_embeddings = current_hidden.clone()
        
        # Decode using HuggingFace native generation!
        inputs_embeds = current_sequence_embeddings.to(self.hf_model.device).to(torch.float16)
        
        # Generation configuration
        max_new_tokens = 256
        
        # We don't have attention_mask since inputs_embeds is just one continuous thought without padding
        outputs = self.hf_model.generate(
            inputs_embeds=inputs_embeds,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=self.tokenizer.pad_token_id if self.tokenizer.pad_token_id else self.tokenizer.eos_token_id,
            eos_token_id=[self.tokenizer.eos_token_id, 151645]
        )
        
        # outputs shape is [batch, max_new_tokens] since inputs_embeds were provided (prompt is not returned)
        generated_ids = outputs[0]
        
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        print(text)
        
        print("\\n========================================")
        
        end_time = time.time()
"""

# We need to replace everything from `# We MUST take the entire sequence` to `print("\n========================================")`
import re
content = re.sub(
    r'# We MUST take the entire sequence.*print\("\\n========================================"\)',
    new_synth.strip(),
    content,
    flags=re.DOTALL
)

with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(content)
