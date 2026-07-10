#!/usr/bin/env python3
"""
verantyx_mcp.py — Verantyx Council MCP サーバー (stdio)
==============================================================================
ベクトル評議会・永遠の記憶・思考の軌跡を MCP (Model Context Protocol) の
ツールとして公開する。依存パッケージなしの素の JSON-RPC 実装。

ツール:
  council_ask    : 質問をベクトル評議会にかけ、必要ならエスカレーションして回答
  memory_search  : 永遠の記憶 (CortexMemory) をベクトル検索
  thought_traces : 保存された思考の軌跡の一覧
  thought_trace  : 特定の軌跡の全ラウンド (各役割の意見・合意・エスカレーション) を返す

登録例 (~/.cursor/mcp.json):
  "verantyx-council": {
    "command": "python3",
    "args": ["/Users/motonishikoudai/verantyx-cli/verantyx_mcp.py"],
    "env": {"JCROSS_GPU": "1", "HF_HUB_OFFLINE": "1"}
  }
"""

import json
import os
import sys
import time

os.environ.setdefault("JCROSS_GPU", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

SERVER_INFO = {"name": "verantyx-council", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "council_ask",
        "description": (
            "Ask the Verantyx vector council. Multiple role agents (Commander/Scouts/Workers) "
            "deliberate by exchanging thought vectors (no text chain-of-thought). "
            "If they fail to agree, larger models are escalated in vector-hijack mode. "
            "Returns the answer, consensus concepts, and a trace_id for the thought trajectory."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to deliberate"},
                "rounds": {"type": "string", "default": "auto",
                           "description": "'auto' (converge/escalate automatically) or a fixed number like '2'"},
                "escalation": {"type": "boolean", "default": True,
                               "description": "Allow escalating to larger models when the council disagrees"},
                "speak_tokens": {"type": ["string", "integer"], "default": "auto",
                                 "description": "'auto' (stop at EOS naturally) or a fixed token cap"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "memory_search",
        "description": "Search the eternal vector memory (CortexMemory). Old memories never die; they only sink.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
    {
        "name": "thought_traces",
        "description": "List saved thought trajectories (deliberation traces) of the council.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
    },
    {
        "name": "thought_trace",
        "description": "Replay one thought trajectory: every round's role opinions, agreement, entropy, escalation.",
        "inputSchema": {
            "type": "object",
            "properties": {"trace_id": {"type": "string", "description": "Trace id (prefix match)"}},
            "required": ["trace_id"],
        },
    },
]

_council = None


def get_council():
    global _council
    if _council is None:
        from verantyx_council import Council
        _council = Council(quiet=True)
    return _council


def call_tool(name, args):
    if name == "council_ask":
        rec = get_council().ask(
            args["question"],
            rounds=str(args.get("rounds", "auto")),
            escalation=bool(args.get("escalation", True)),
            speak_tokens=args.get("speak_tokens", "auto"))
        return {
            "answer": rec["answer"],
            "speaker": rec["speaker"],
            "concepts": rec["concepts"],
            "trace_id": rec["trace_id"],
            "escalation_level": rec["escalation_level"],
            "rounds": [{"round": r["round"], "agreement": r["agreement"],
                        "entropy": r["entropy"]} for r in rec["rounds"]],
            "elapsed_s": rec["elapsed_s"],
        }
    if name == "memory_search":
        return {"hits": get_council().memory_search(args["query"], k=int(args.get("k", 3)))}
    if name == "thought_traces":
        from verantyx_council import ThoughtTrace
        recs = ThoughtTrace().list(limit=int(args.get("limit", 10)))
        return {"traces": [{"trace_id": r["trace_id"],
                            "ts": time.strftime("%Y-%m-%d %H:%M", time.localtime(r["ts"])),
                            "question": r["question"], "answer": r["answer"],
                            "escalation_level": r["escalation_level"]} for r in recs]}
    if name == "thought_trace":
        from verantyx_council import ThoughtTrace
        rec = ThoughtTrace().load(args["trace_id"])
        if rec is None:
            return {"error": f"trace '{args['trace_id']}' not found"}
        return rec
    raise ValueError(f"unknown tool: {name}")


def handle(msg):
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        try:
            result = call_tool(params.get("name"), params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            }}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"error: {e}"}], "isError": True,
            }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main():
    # RustエンジンのネイティブprintlnもJSON-RPCを壊さないよう、fdレベルで退避:
    # fd1への書き込み (Python/Rust問わず) は全てstderrへ、RPCは複製したfdへ書く
    rpc_fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    rpc_out = os.fdopen(rpc_fd, "w")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            rpc_out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            rpc_out.flush()


if __name__ == "__main__":
    main()
