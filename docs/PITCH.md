# Pitch kit (Show HN / X / Reddit / Zenn)

Use these verbatim. Keep claims honest — link benches instead of inventing numbers.

## One-liner

**Tiny always-on router. Big model only when needed. Memory that survives reboot.**

日本語: **常駐は小さいルーターだけ。大きなモデルは必要なときだけ。記憶は再起動をまたぐ。**

## Show HN title ideas

1. Show HN: Verantyx – keep a 0.5B router resident, summon big local models only when needed  
2. Show HN: Local AI harness – RAM-light routing + memory that survives reboot  
3. Show HN: Vector council CLI – cheaper multi-agent medium, not an accuracy booster

## Short body (~800 chars)

Verantyx is a local CLI harness for people who want strong on-device models without parking a 7B–70B in VRAM all day.

- ~0.5B router stays resident (classify / route / remember)
- Large speakers (Ollama / HF / LM Studio / local) speak **once** when summoned
- Eternal memory lives outside the chat context window (survives quit & reboot)
- Optional vector council: a cheaper agreement medium than chatty NL multi-agent loops

Honest limit: on large *secret* fair benches with the same speaker, council ≈ router.  
But **company + eternal memory** is a different claim: on our 26-item numeric/logic/fact focus set, Qwen2.5 ~0.5B + structure + memory (**80.8%**) beat naked Qwen3.5:0.8B (**73.1%**). Same-size uplift also holds; same-gen 2B solo is still ahead. Vectors still beat NL debate as a medium on our benches.

Try with zero weights:

```
docker build -t verantyx:demo . && docker run --rm -it verantyx:demo
```

Repo: https://github.com/Ag3497120/verantyx-cli  
Demo script: https://github.com/Ag3497120/verantyx-cli/blob/main/docs/DEMO.md  
Benches: https://github.com/Ag3497120/verantyx-cli/blob/main/benchmarks/README.md

## Tweet / X

Tiny always-on router. Big model only when needed. Memory that survives reboot.

Local CLI: keep ~0.5B warm, summon Ollama/HF once, remember across restarts.

`docker build -t verantyx:demo . && docker run --rm -it verantyx:demo`

https://github.com/Ag3497120/verantyx-cli

## What not to say

- “Beats 9B / GPT / Claude on accuracy”
- “Council makes any model much smarter”
- Fake GIF / unrelated UI screenshots
