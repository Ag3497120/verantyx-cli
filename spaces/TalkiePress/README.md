---
title: "TalkiePress: Modern News in 1930"
emoji: 📰
colorFrom: gray
colorTo: yellow
sdk: gradio
sdk_version: "5.15.0"
python_version: "3.10"
app_file: app.py
pinned: false
---

# TalkiePress — Modern News in 1930

Generate a 1930s-style newspaper column from a short modern news prompt.

## Hardware

The default model is a **13B Q4 GGUF**. Free **cpu-basic** Spaces often run out of memory when loading it. For real inference, upgrade the Space to a GPU (L4 / A10G) in Settings.

The Gradio UI still **starts on cpu-basic** (model load is deferred). If the model cannot load, a demo layout plus the error message is shown.

## Environment (optional)

| Variable | Default | Meaning |
|---|---|---|
| `TALKIE_GGUF_REPO` | `kofdai/talkie-1930-13b-it-mlx-8bit` | Hub repo for the GGUF |
| `TALKIE_GGUF_FILE` | `talkie-1930-13b-it-Q4_K_M.gguf` | Filename inside that repo |
| `GGUF_MODEL_PATH` | — | Local path override |
| `TALKIE_N_THREADS` | `2` | llama.cpp threads |
| `TALKIE_MAX_TOKENS` | `400` | Generation length |

## Local run

```bash
pip install -r requirements.txt
python app.py
```
