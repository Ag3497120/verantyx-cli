with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()
import re
text = text.replace('messages = [{"role": "system", "content": "Decode the preceding telepathic thought vector."}]', 'messages = [{"role": "system", "content": "Decode the preceding telepathic thought vector."}, {"role": "user", "content": "Decode."}]')
with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
