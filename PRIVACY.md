# Privacy

Verantyx is designed as a **local-first** runtime. This note describes what typically stays on your machine and what may leave it. It is not a legal privacy policy for a hosted service — there is no Verantyx cloud that stores your chats by default.

## What stays local

- Chat turns, agent plans, and “eternal memory” vectors/indexes under `.verantyx_chrono/` (and related gitignored dirs — see [`SECURITY.md`](SECURITY.md))
- Screen / vault / persona data you enable locally
- Converted weights (`.jgen`, etc.) and engine binaries you build
- Skill / reflex stores written by local feedback learning (stored on disk, not auto-uploaded)

Git ignores these paths so they should not appear in normal commits. Still: do not force-add them.

## What may leave the machine

| Channel | When | What can leave |
|---|---|---|
| **Hugging Face downloads** | `setup` / forge / `huggingface_hub` pulls | Model/tokenizer requests to HF (and their CDN); your HF token if you configure one |
| **Ollama / LM Studio / other bridges** | You point Verantyx at those backends | Prompts and completions to **those** local or remote endpoints as configured |
| **Web / browser tools** | Agent fetches URLs | Outbound HTTP(S) to sites you (or the agent) open |
| **Optional API feedback / remote speakers** | Only if **you** enable a cloud or HTTP API backend | Prompt/feedback text to that API — not required for core local Omni |

There is no built-in product telemetry dashboard claimed here. If a future optional feedback switch exists, treat it as opt-in and read the flag/docs before enabling.

## Memory contents (sensitivity)

Eternal memory may retain:

- Conversation text and embeddings
- Task/tool traces
- Screen or vault snippets if you used those features
- Learned skill plans derived from your feedback

Anyone with filesystem access to `.verantyx_chrono/` can read that history. Wipe steps: [`SECURITY.md`](SECURITY.md).

## Models vs code

Repository **code** is under [`LICENSE`](LICENSE) (MIT). **Upstream model weights and tokenizers keep their own licenses** (Qwen, GLM, Ornith, etc.). Downloading a model does not relicense it as MIT. See the license table in the README.
