with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()

new_system_prompt = """        system_prompt = (
            "You are a precise code patch generator. "
            "Decode the preceding telepathic thought vector into a strict SEARCH/REPLACE block. "
            "Do NOT output the entire file. Output ONLY the lines that need to be changed.\\n"
            "Format exactly as follows:\\n"
            "File: <relative/path/to/file>\\n"
            "[SEARCH]\\n<original lines exactly as they appear>\\n"
            "[REPLACE]\\n<new modified lines>\\n"
            "[/REPLACE]"
        )"""

import re
text = re.sub(r'        system_prompt = \([^)]+\)', new_system_prompt, text, flags=re.DOTALL)

with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
