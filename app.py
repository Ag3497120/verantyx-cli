import gradio as gr
import subprocess
import os
import sys

def run_verantyx(prompt):
    if not prompt.strip():
        yield "Please enter a task description."
        return

    # Use ansi2html to convert terminal colors to HTML
    try:
        from ansi2html import Ansi2HTMLConverter
        conv = Ansi2HTMLConverter(dark_bg=True)
    except ImportError:
        yield "Error: ansi2html is not installed. Please add it to requirements.txt"
        return

    script_path = os.path.join(os.path.dirname(__file__), "cli", "scripts", "bucket_relay_swarm_experimental.py")
    
    # Start the subprocess
    process = subprocess.Popen(
        [sys.executable, script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1 # Line buffered
    )
    
    # Send the user prompt and close stdin (since the script reads until EOF)
    process.stdin.write(prompt)
    process.stdin.close()
    
    output_html = "<div style='background-color: black; color: white; padding: 10px; font-family: monospace; white-space: pre-wrap;'>"
    yield output_html + "Starting Verantyx Ambient Telepathy Pipeline...<br></div>"
    
    raw_output = ""
    # Stream the output line by line
    for line in iter(process.stdout.readline, ''):
        raw_output += line
        # Convert the accumulated raw output to HTML
        html_chunk = conv.convert(raw_output, full=False)
        yield f"<div style='background-color: black; color: white; padding: 10px; font-family: monospace; white-space: pre-wrap;'>{html_chunk}</div>"
        
    process.stdout.close()
    process.wait()

# Create the Gradio Interface
with gr.Blocks(title="Verantyx: God Mode (Telepathic Swarm)") as demo:
    gr.Markdown("# 🧠 Verantyx: Telepathic Swarm Architecture")
    gr.Markdown("Watch the internal thought processes (Latent Resonance Search, Vector Diffusion) in real-time. The Qwen 0.5B multi-agent swarm communicates through 1024D vectors instead of text.")
    
    with gr.Row():
        with gr.Column(scale=1):
            prompt_input = gr.Textbox(
                label="Task Description (Prompt)", 
                placeholder="Enter a task to inject into the swarm's Ambient Space...",
                lines=3
            )
            submit_btn = gr.Button("Inject Thought (Run)", variant="primary")
            
    with gr.Row():
        with gr.Column(scale=1):
            # We use an HTML component to render the ANSI-colored terminal logs
            output_display = gr.HTML(label="God Mode Terminal Log")
            
    submit_btn.click(
        fn=run_verantyx,
        inputs=prompt_input,
        outputs=output_display
    )

if __name__ == "__main__":
    demo.queue().launch()
