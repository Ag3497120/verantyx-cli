# Security

Verantyx is a **local** AI runtime that can run shell, touch files, and drive a browser when you use Agent / Omni tools. Treat it like any powerful local automation: the machine boundary is yours to defend.

## Threat model (lite)

| Surface | Risk | Default posture |
|---|---|---|
| **Shell** | Arbitrary commands on your user account | Confirm before run (`y/N`). `--yes` / auto-approve skips prompts — **high risk** |
| **Files** | Read/write/edit in reachable paths | Confirm on write/edit |
| **Web / browser** | Network fetch; page content may be untrusted | Agent uses real WebKit-style fetch where enabled — do not point at secrets |
| **Eternal memory** | Long-lived local store of chats, tasks, screen notes, vectors | Stays on disk under data dirs below; not pushed with `git` |
| **Model bridges** | Calls to local Ollama / LM Studio / HF downloads | Network only when you configure downloads or remote backends |
| **Optional API feedback** | If enabled, prompts/feedback may leave the machine | Off unless you turn it on — see [`PRIVACY.md`](PRIVACY.md) |

This is **not** a sandbox. Compromised prompts, malicious pages, or reckless `--yes` can harm the host.

## Data directories (eternal memory & friends)

Typically next to the repo / cwd (gitignored; do not commit):

| Path | Contents (typical) |
|---|---|
| `.verantyx_chrono/` | Eternal memory vectors/indexes, vault, lexicon caches, model registry |
| `.verantyx_profile/` | Local profile / persona-related state |
| `.openclaw/jcross_vault/` | Vault-related local data (if used) |
| `verantyx.config.json` | Local config |
| HuggingFace / Ollama caches | Upstream weight caches under their usual home dirs |

Exact filenames evolve; if unsure, inspect those directories before sharing a machine image.

## How to wipe local memory

Stop Verantyx first. Then remove the local data dirs you no longer want, for example:

```bash
# From the repo root — irreversible
rm -rf .verantyx_chrono .verantyx_profile
rm -f verantyx.config.json my_clone.memory
# Optional, if present:
rm -rf .openclaw/jcross_vault
```

Model **weights** (`.jgen`, GGUF, HF snapshots under `~/.cache/huggingface`, Ollama blobs, etc.) are separate; delete those only if you intend to remove models.

## Approval / YOLO danger

- Prefer interactive confirmations for shell and file writes.
- Flags like `--yes` (auto-approve) are **yolo mode**: convenient for demos, unsafe on shared or sensitive machines.
- Do not run Verantyx Agent as root / Administrator.
- Do not paste secrets into chats that may be written into eternal memory.

## Reporting a vulnerability

Please **do not** open a public issue for exploitable bugs that enable remote or local privilege abuse.

Open a **private** GitHub security advisory on this repository, or email:

`security@example.com` <!-- TODO: replace with a real contact -->

Include: affected version/commit, reproduction steps, and impact. We will acknowledge when we can; this project is research-paced.

## Related

- [`PRIVACY.md`](PRIVACY.md) — what stays local vs what may leave  
- [`LICENSE`](LICENSE) — code license (MIT); **model weights are not MIT**
