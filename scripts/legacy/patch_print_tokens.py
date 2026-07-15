with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

patch = """            if step >= prompt_tokens.len() - 1 {
                generated.push(best_token);
                print!("{} ", best_token);
                use std::io::Write;
                std::io::stdout().flush().unwrap();
                current_token = best_token;"""

import re
content = re.sub(r'            if step >= prompt_tokens\.len\(\) - 1 \{\n                generated\.push\(best_token\);\n                current_token = best_token;', patch, content)

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
