import torch
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-9b-it")
gemma_template = "{{ bos_token }}{% for message in messages %}{% if (message['role'] == 'assistant') %}{% set role = 'model' %}{% else %}{% set role = message['role'] %}{% endif %}{{ '<start_of_turn>' + role + '\n' + message['content'] | trim + '<end_of_turn>\n' }}{% endfor %}{% if add_generation_prompt %}{{'<start_of_turn>model\n'}}{% endif %}"

tokenizer.chat_template = gemma_template
chat_messages = [{"role": "user", "content": "Hello"}]
encoded = tokenizer.apply_chat_template(chat_messages, return_tensors="pt", add_generation_prompt=True, return_dict=False)

if isinstance(encoded, dict):
    input_ids = encoded['input_ids']
else:
    input_ids = encoded

print("Tokens:", input_ids)
print("Decoded:", tokenizer.decode(input_ids[0]))
for token_id in input_ids[0]:
    print(f"{token_id}: {tokenizer.decode([token_id])}")
