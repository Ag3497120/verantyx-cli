with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()

text = text.replace(
    'inputs_embeds = torch.cat([prompt_embeds, raw_thought_embeds], dim=1)',
    'inputs_embeds = torch.cat([prompt_embeds, raw_thought_embeds.to(prompt_embeds.dtype)], dim=1)\n        inputs_embeds = inputs_embeds.to(self.hf_model.dtype)'
)

with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
