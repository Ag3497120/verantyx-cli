with open("jcross_engine_glm/src/bin/test_glm.rs", "r") as f:
    content = f.read()

import re
content = re.sub(r'let prompt = vec!\[.*?\];', 'let prompt = vec![151331];', content)

with open("jcross_engine_glm/src/bin/test_glm.rs", "w") as f:
    f.write(content)
