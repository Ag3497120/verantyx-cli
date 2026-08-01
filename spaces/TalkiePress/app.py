"""TalkiePress — Gradio Space entrypoint.

Designed to *boot* on Hugging Face Spaces cpu-basic without crashing at import.
Heavy GGUF download/load is deferred until the first generation request.
"""
from __future__ import annotations

import os
import threading
import traceback

import gradio as gr

# Optional heavy deps — never fail the Space boot if missing.
try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None  # type: ignore

try:
    from huggingface_hub import hf_hub_download
except ImportError:  # pragma: no cover
    hf_hub_download = None  # type: ignore

from tokenizer_spaces import build_tokenizer

REPO_ID = os.environ.get(
    "TALKIE_GGUF_REPO", "kofdai/talkie-1930-13b-it-mlx-8bit"
)
FILENAME = os.environ.get("TALKIE_GGUF_FILE", "talkie-1930-13b-it-Q4_K_M.gguf")
N_CTX = int(os.environ.get("TALKIE_N_CTX", "2048"))
N_THREADS = int(os.environ.get("TALKIE_N_THREADS", "2"))
MAX_TOKENS_DEFAULT = int(os.environ.get("TALKIE_MAX_TOKENS", "400"))

print("Loading tiktoken BPE vocabulary...")
tokenizer = build_tokenizer("vocab.txt", style="it")

historical_model = None
model_path: str | None = None
model_error: str | None = None
model_load_lock = threading.Lock()


def _resolve_model_path() -> str:
    global model_path, model_error
    if model_path and os.path.isfile(model_path):
        return model_path
    local = os.environ.get("GGUF_MODEL_PATH", "./talkie-1930-13b-it-Q4_K_M.gguf")
    if os.path.isfile(local):
        model_path = local
        return model_path
    if hf_hub_download is None:
        raise RuntimeError("huggingface_hub is not installed")
    print(f"Downloading GGUF {REPO_ID}/{FILENAME} (first request only)...")
    model_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)
    return model_path


def get_model():
    """Lazy-load llama.cpp model. Raises with a clear message on failure."""
    global historical_model, model_error
    if historical_model is not None:
        return historical_model
    if Llama is None:
        raise RuntimeError(
            "llama-cpp-python is not installed. "
            "Rebuild the Space with requirements.txt."
        )
    with model_load_lock:
        if historical_model is not None:
            return historical_model
        try:
            path = _resolve_model_path()
            print(f"Loading GGUF from {path}...")
            historical_model = Llama(
                model_path=path,
                n_ctx=N_CTX,
                n_threads=N_THREADS,
                verbose=False,
            )
            model_error = None
            return historical_model
        except Exception as e:
            model_error = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            raise RuntimeError(
                "Failed to load Talkie GGUF. Free cpu-basic often OOMs on 13B; "
                "upgrade Space hardware (L4/A10G) or set TALKIE_GGUF_* to a "
                f"smaller model. Detail: {model_error}"
            ) from e


def _demo_article(event: str, headline: str, subtitle: str) -> str:
    """Offline fallback so the Space stays usable while the model is unavailable."""
    body = (
        f"Yesterday, {event} Authorities and townsfolk alike spoke of the matter "
        "with a mixture of wonder and caution, as is the custom of our times. "
        "Further particulars are awaited from correspondents abroad."
    )
    return f"""<div style="background-color: #f4ecd8 !important; color: #2c241b !important; padding: 20px; font-family: serif;">
        <h1 style="text-align: center; font-size: 2.5em; border-bottom: 2px solid #1a1a1a; margin-bottom: 5px; color: #2c241b !important;">{headline}</h1>
        <h3 style="text-align: center; font-size: 1.5em; font-style: italic; margin-top: 0; padding-bottom: 15px; border-bottom: 4px double #1a1a1a; color: #2c241b !important;">{subtitle}</h3>
        <div style="column-count: 2; column-gap: 20px; column-rule: 1px solid #3b2f2f; margin-top: 20px; font-size: 1.1em; line-height: 1.6; color: #2c241b !important;">
            <p style="color: #2c241b !important;"><strong>NEW YORK — </strong>{body}</p>
            <p style="color: #666 !important; font-size: 0.9em;"><em>(Demo layout — model not loaded on this hardware.)</em></p>
        </div>
    </div>"""


class HistoricalReporterAgent:
    @staticmethod
    def generate_article(news_text, max_tokens=MAX_TOKENS_DEFAULT):
        first_sentence = (
            news_text.split(".")[0] + "." if "." in news_text else news_text[:100]
        )
        headline = "Special Report"
        subtitle = "Authorities Investigating Strange Occurrences"
        event = first_sentence

        prompt = f"""<|user|>
Write a 1930s newspaper article about this event: {event}
<|end|>
<|assistant|>
THE NEW YORK TIMES - October 24, 1930

[HEADLINE]: {headline}
[SUBTITLE]: {subtitle}
[BYLINE]: By Arthur Conan, Senior Correspondent

NEW YORK — Yesterday, {event} """

        try:
            llm = get_model()
        except Exception as e:
            yield _demo_article(event, headline, subtitle) + (
                f"<pre style='color:#a00;white-space:pre-wrap'>{e}</pre>"
            )
            return

        input_ids = tokenizer.encode(prompt, allowed_special="all")
        end_id = tokenizer.encode("<|end|>", allowed_special="all")[0]
        generator = llm.generate(tokens=input_ids, temp=0.7, top_p=0.9)

        generated_text = ""
        generated_count = 0
        for token_id in generator:
            if token_id == end_id:
                break
            token_str = tokenizer.decode([token_id])
            if token_str:
                generated_text += token_str
                generated_count += 1
            if generated_count >= max_tokens:
                break

            clean_text = generated_text
            for stop_phrase in [
                "[HEADLINE]",
                "[SUBTITLE]",
                "THE NEW YORK TIMES",
                "<|end|>",
            ]:
                if stop_phrase in clean_text:
                    clean_text = clean_text[: clean_text.find(stop_phrase)]

            paragraphs = clean_text.strip().split("\n\n")
            formatted = "".join(
                f"<p>{p.replace(chr(10), '<br>')}</p>"
                for p in paragraphs
                if p.strip()
            )
            yield f"""<div style="background-color: #f4ecd8 !important; color: #2c241b !important; padding: 20px; font-family: serif;">
        <h1 style="text-align: center; font-size: 2.5em; border-bottom: 2px solid #1a1a1a; margin-bottom: 5px; color: #2c241b !important;">{headline}</h1>
        <h3 style="text-align: center; font-size: 1.5em; font-style: italic; margin-top: 0; padding-bottom: 15px; border-bottom: 4px double #1a1a1a; color: #2c241b !important;">{subtitle}</h3>
        <div style="column-count: 2; column-gap: 20px; column-rule: 1px solid #3b2f2f; margin-top: 20px; font-size: 1.1em; line-height: 1.6; color: #2c241b !important;">
            <p style="color: #2c241b !important;"><strong>NEW YORK — </strong>Yesterday, {event} {formatted}</p>
        </div>
    </div>"""


class Orchestrator:
    def process(self, news_text):
        with model_load_lock:
            yield (
                "Initializing Talkie engine…",
                "<div style='color: #888;'>Preparing inference…</div>",
            )
            display_str = "HEADLINE: Special Report\nEVENT: Generating…"
            for html_chunk in HistoricalReporterAgent.generate_article(
                news_text, max_tokens=MAX_TOKENS_DEFAULT
            ):
                yield display_str, html_chunk


orchestrator = Orchestrator()


def ui_handler(news_text):
    if not news_text or not str(news_text).strip():
        yield "Please enter a news item.", "<div>Please enter a news item.</div>"
        return
    for result in orchestrator.process(news_text):
        yield result


with gr.Blocks(
    theme=gr.themes.Monochrome(),
    title="TalkiePress — Modern News in 1930",
) as app:
    gr.Markdown("# TalkiePress: Modern News in 1930")
    gr.Markdown(
        "Turn a short modern headline into a 1930s-style newspaper column. "
        "On free CPU Spaces the 13B GGUF may not fit — upgrade hardware in "
        "Settings, or the UI will show a demo layout with the error detail."
    )
    with gr.Row():
        with gr.Column(scale=2):
            news_input = gr.Textbox(
                label="Current News (short factual prompt)", lines=5
            )
            generate_btn = gr.Button("Generate 1930s Article", variant="primary")
            abstract_output = gr.Textbox(label="Status", interactive=False, lines=2)
        with gr.Column(scale=3):
            article_output = gr.HTML(label="1930s Newspaper Layout")

    generate_btn.click(
        fn=ui_handler,
        inputs=[news_input],
        outputs=[abstract_output, article_output],
    )

# Spaces looks for a top-level `demo` or launches `app` via app_file.
demo = app

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
