"""
app.py — Verantyx Space サーバー
=================================
FastAPI + SSE。Qwen 0.5B (jgen / Rustエンジン) の評議会を実行し、
議論の内部状態 (意見ベクトル・合意・摂動テスト) をリアルタイムで
フロントの 3D シーンへストリームする。
"""
import json
import queue
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Verantyx God Mode")

_council = None
_lock = threading.Lock()   # CPU 2vCPU なので同時実行は1件に直列化


def get_council():
    global _council
    if _council is None:
        from space_council import SpaceCouncil
        _council = SpaceCouncil()
    return _council


class Ask(BaseModel):
    question: str
    baseline: bool = True
    rounds: int = 2  # 無料CPU Spaceでは1フォワード~10秒のため既定2ラウンド


@app.post("/api/ask")
def ask(body: Ask):
    q = (body.question or "").strip()[:500]
    if not q:
        return {"error": "empty question"}

    ch = queue.Queue()

    def run():
        try:
            with _lock:
                council = get_council()
                for ev in council.deliberate(q, max_rounds=max(1, min(body.rounds, 4))):
                    ch.put(ev)
                if body.baseline:
                    ch.put({"type": "status", "msg": "比較: 同じ0.5Bに評議会なしで直接回答させる"})
                    ch.put(council.baseline(q))
            ch.put({"type": "done"})
        except Exception as e:
            ch.put({"type": "error", "msg": str(e)[:300]})
            ch.put({"type": "done"})

    threading.Thread(target=run, daemon=True).start()

    def stream():
        while True:
            ev = ch.get()
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if ev.get("type") == "done":
                break

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/health")
def health():
    c = get_council()
    return {"ok": True, "model": "Qwen2.5-0.5B-Instruct (JGEN / Rust engine)",
            "hidden": c.brain.hidden, "load_s": round(c.load_s, 1)}


@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
