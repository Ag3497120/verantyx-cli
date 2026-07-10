with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

patch = """        let project_any = |names: &[&str], input: &Tensor| -> Result<Tensor, String> {
            let mut last_err = String::new();
            for name in names {
                match self.project_vector_gpu(name, input) {
                    Ok(res) => return Ok(res),
                    Err(e) => { last_err = format!("{} error: {}", name, e); }
                }
            }
            Err(format!("None of the layers found: {:?}. Last error: {}", names, last_err))
        };"""

import re
content = re.sub(r'let project_any = \|names: &\[&str\], input: &Tensor\| -> Result<Tensor, String> \{.*?Err\(format!\("None of the layers found: \{\:\?\}", names\)\)\n\s*\};', patch, content, flags=re.DOTALL)

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
