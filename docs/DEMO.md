# 60-second demo (honest)

No stock footage. No fake GIFs. Only paths that work in this repo today.

**Pitch to feel:** tiny brain always on → big brain speaks once → memory survives reboot.

日本語の短い説明は下段。

---

## A. Zero weights (recommended first)

### Docker

```bash
cd verantyx-cli
docker build -t verantyx:demo .
docker run --rm -it verantyx:demo
```

Expected: a few prompts labeled `task` / `chat?` from the classify safety net. No model download.

### Local Python

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/smoke_router_classify.py --no-model
```

Recorder helper:

```bash
./scripts/record_demo.sh --no-model
```

---

## B. With router weights (the “memory survives reboot” beat)

```bash
python3 verantyx.py
# Omni → ask one short question → quit
python3 verantyx.py
# ask about the previous turn / check memory — it should still be there
```

Optional classify with weights:

```bash
python3 scripts/smoke_router_classify.py
```

---

## C. Record a real clip (optional)

```bash
asciinema rec /tmp/verantyx-demo.cast
./scripts/record_demo.sh --no-model
exit
# convert with your usual tool → assets/ only if the output is real
```

---

## Do not

- Paste unrelated product UI GIFs
- Invent benchmark numbers in the demo
- Leave “demo coming soon” with no commands

---

## 日本語まとめ

1. **重みなし:** `docker build -t verantyx:demo . && docker run --rm -it verantyx:demo`  
2. **重みあり:** `python3 verantyx.py` → Omni で一言 → 終了 → 再起動して記憶が残るか確認  
3. 偽GIF禁止。手順の正本はこのページ。
