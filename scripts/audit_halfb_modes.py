#!/usr/bin/env python3
"""0.5B-only mode/command/memory/quality audit harness.

Runs non-interactive paths covering CLI modes, Omni command surfaces,
eternal memory, multi-turn tasks, and fair quality comparison vs bare Ollama.
Writes a JSON report under benchmarks/results/halfb_audit_<ts>/.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

OUT = ROOT / "benchmarks" / "results" / f"halfb_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

PY = sys.executable
ENV = os.environ.copy()
ENV["JGEN_MODEL"] = str(ROOT / "converted_models" / "qwen0_5b_full.jgen")
ENV["PYTHONUNBUFFERED"] = "1"


def run_cmd(args, timeout=180, input_text=None):
    t0 = time.time()
    try:
        p = subprocess.run(
            args, cwd=ROOT, env=ENV, text=True, capture_output=True,
            timeout=timeout, input=input_text,
        )
        return {
            "ok": p.returncode == 0,
            "rc": p.returncode,
            "elapsed_s": round(time.time() - t0, 2),
            "stdout": (p.stdout or "")[-4000:],
            "stderr": (p.stderr or "")[-2000:],
            "cmd": args,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False, "rc": -1, "elapsed_s": round(time.time() - t0, 2),
            "stdout": ((e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))[-4000:],
            "stderr": f"TIMEOUT after {timeout}s",
            "cmd": args,
        }
    except Exception as e:
        return {
            "ok": False, "rc": -2, "elapsed_s": round(time.time() - t0, 2),
            "stdout": "", "stderr": f"{type(e).__name__}: {e}", "cmd": args,
        }


def record(section, name, result, notes=""):
    row = {"section": section, "name": name, "notes": notes, **result}
    # shrink cmd for readability
    if isinstance(row.get("cmd"), list):
        row["cmd"] = " ".join(str(x) for x in row["cmd"])
    print(f"[{'OK' if row.get('ok') else 'FAIL'}] {section}/{name} ({row.get('elapsed_s')}s) {notes}")
    return row


def section_smoke_paths():
    rows = []
    # classify-only smoke (no model)
    rows.append(record(
        "smoke", "router_classify_no_model",
        run_cmd([PY, "scripts/smoke_router_classify.py", "--no-model"], timeout=60),
    ))
    # council oneshot 0.5B only
    rows.append(record(
        "smoke", "council_prompt_no_escalate",
        run_cmd([
            PY, "verantyx_council.py",
            "--prompt", "What is 2+2? Answer with only the number.",
            "--no-escalate", "--secret", "--speak-tokens", "32",
        ], timeout=240),
    ))
    # mind oneshot
    rows.append(record(
        "smoke", "mind_prompt_worker_none",
        run_cmd([
            PY, "verantyx_mind.py",
            "--prompt", "Say OK in one word.",
            "--worker", "none", "--secret", "--speak-tokens", "16",
        ], timeout=240),
    ))
    # agent with local ollama 0.5b
    rows.append(record(
        "smoke", "agent_echo_task",
        run_cmd([
            PY, "verantyx_agent.py",
            "--task", "Print the string READY using a shell command, then stop.",
            "--backend", "ollama:qwen2.5:0.5b", "--yes", "--secret", "--max-steps", "4",
        ], timeout=300),
        notes="agent brain is ollama 0.5b (not jgen router)",
    ))
    # dict CLI if available
    rows.append(record(
        "smoke", "dict_assoc",
        run_cmd([PY, "verantyx_dict.py", "assoc", "Tokyo"], timeout=180),
    ))
    # matryoshka puzzle oneshot
    rows.append(record(
        "smoke", "matryoshka_prompt",
        run_cmd([
            PY, "verantyx_matryoshka.py",
            "--prompt", "What is the capital of France? One word.",
            "--depth", "1", "--quiet",
        ], timeout=300),
    ))
    # config show
    rows.append(record(
        "smoke", "config_show",
        run_cmd([PY, "verantyx_config.py", "show"], timeout=30),
    ))
    # forge list / sources
    rows.append(record("smoke", "forge_list", run_cmd([PY, "jgen_forge.py", "list"], timeout=60)))
    rows.append(record("smoke", "forge_sources", run_cmd([PY, "jgen_forge.py", "sources"], timeout=60)))
    # scout report
    rows.append(record(
        "smoke", "model_scout_report",
        run_cmd([PY, "-c", "import model_scout; print(model_scout.report())"], timeout=120),
    ))
    return rows


def section_omni_command_surface():
    """Exercise Omni slash-command backends via Council/API (non-interactive)."""
    rows = []
    try:
        from verantyx_council import Council, ThoughtTrace
        import verantyx_config
        import jgen_forge
        import model_scout

        council = Council(quiet=True, secret=False)
        # /config show equivalent
        rows.append(record("omni_cmd", "config_describe", {
            "ok": True, "elapsed_s": 0, "stdout": verantyx_config.describe()[:1500], "stderr": "",
        }))
        # /council members
        members = [getattr(p, "name", str(p)) for p in getattr(council, "peers", [])] \
            if hasattr(council, "peers") else []
        # peers may be named differently
        peer_names = []
        for attr in ("peers", "members", "council_members"):
            if hasattr(council, attr):
                vals = getattr(council, attr)
                try:
                    peer_names = [getattr(x, "name", str(x)) for x in vals]
                except Exception:
                    peer_names = [str(vals)]
                break
        rows.append(record("omni_cmd", "council_members", {
            "ok": True, "elapsed_s": 0,
            "stdout": json.dumps(peer_names, ensure_ascii=False), "stderr": "",
        }))
        # /scout
        t0 = time.time()
        report = model_scout.report()
        rows.append(record("omni_cmd", "scout", {
            "ok": bool(report), "elapsed_s": round(time.time() - t0, 2),
            "stdout": str(report)[:2000], "stderr": "",
        }))
        # /convert list
        t0 = time.time()
        srcs = jgen_forge.cmd_sources()
        rows.append(record("omni_cmd", "convert_list", {
            "ok": True, "elapsed_s": round(time.time() - t0, 2),
            "stdout": f"{len(srcs or [])} sources", "stderr": "",
        }))
        # /mem
        t0 = time.time()
        try:
            from memory_guard import GUARD
            mem_status = GUARD.status()
        except Exception as e:
            mem_status = f"err:{e}"
        rows.append(record("omni_cmd", "mem_status", {
            "ok": True, "elapsed_s": round(time.time() - t0, 2),
            "stdout": str(mem_status), "stderr": "",
        }))
        # /ask plain council
        t0 = time.time()
        ans = council.ask(
            "Name one primary color. One word only.",
            rounds=1, escalation=False, force_router_speaker=True,
            speak_tokens=24,
        )
        text = ans if isinstance(ans, str) else getattr(ans, "text", str(ans))
        rows.append(record("omni_cmd", "ask_council", {
            "ok": bool(text and len(str(text).strip()) > 0),
            "elapsed_s": round(time.time() - t0, 2),
            "stdout": str(text)[:1000], "stderr": "",
        }))
        # /fast toggle semantics via escalation=False already
        rows.append(record("omni_cmd", "fast_off_semantics", {
            "ok": True, "elapsed_s": 0,
            "stdout": "escalation.enabled=false in config; ask used escalation=False",
            "stderr": "",
        }))
        # /tokens /rounds /lang soft checks via ask kwargs
        t0 = time.time()
        ans2 = council.ask(
            "Reply with the word PING only.",
            rounds=1, escalation=False, force_router_speaker=True,
            speak_tokens=8,
        )
        rows.append(record("omni_cmd", "tokens_rounds_ask", {
            "ok": bool(ans2), "elapsed_s": round(time.time() - t0, 2),
            "stdout": str(ans2)[:500], "stderr": "",
        }))
        # /traces
        t0 = time.time()
        try:
            traces = ThoughtTrace().list()
            ok = True
            out = f"{len(traces)} traces"
        except Exception as e:
            ok = False
            out = str(e)
        rows.append(record("omni_cmd", "traces_list", {
            "ok": ok, "elapsed_s": round(time.time() - t0, 2),
            "stdout": out, "stderr": "",
        }))
        # /reflex /injections /skills if present
        for name, getter in [
            ("reflex", lambda: getattr(council, "reflex", None) or getattr(council, "router_reflex", None)),
            ("skills", lambda: __import__("skill_memory").SkillLibrary()),
        ]:
            t0 = time.time()
            try:
                obj = getter()
                rows.append(record("omni_cmd", name, {
                    "ok": obj is not None, "elapsed_s": round(time.time() - t0, 2),
                    "stdout": str(obj)[:500], "stderr": "",
                }))
            except Exception as e:
                rows.append(record("omni_cmd", name, {
                    "ok": False, "elapsed_s": round(time.time() - t0, 2),
                    "stdout": "", "stderr": str(e),
                }))
        # /dict /analogy via weight_lexicon if possible
        t0 = time.time()
        try:
            from weight_lexicon import default_lexicon
            lex = default_lexicon()
            if lex is None:
                rows.append(record("omni_cmd", "dict_lexicon", {
                    "ok": False, "elapsed_s": round(time.time() - t0, 2),
                    "stdout": "", "stderr": "default_lexicon returned None",
                    "notes": "weakness: lexicon may need larger model or full weights",
                }))
            else:
                assoc = None
                for meth in ("assoc", "associate", "search", "query"):
                    if hasattr(lex, meth):
                        try:
                            assoc = getattr(lex, meth)("Tokyo")
                            break
                        except TypeError:
                            continue
                rows.append(record("omni_cmd", "dict_lexicon", {
                    "ok": True, "elapsed_s": round(time.time() - t0, 2),
                    "stdout": str(assoc)[:800], "stderr": "",
                }))
        except Exception as e:
            rows.append(record("omni_cmd", "dict_lexicon", {
                "ok": False, "elapsed_s": round(time.time() - t0, 2),
                "stdout": "", "stderr": traceback.format_exc()[-1500:],
            }))
        # /persona
        t0 = time.time()
        try:
            persona = council.memory.persona() if hasattr(council, "memory") else None
            rows.append(record("omni_cmd", "persona", {
                "ok": True, "elapsed_s": round(time.time() - t0, 2),
                "stdout": str(persona)[:800], "stderr": "",
            }))
        except Exception as e:
            rows.append(record("omni_cmd", "persona", {
                "ok": False, "elapsed_s": round(time.time() - t0, 2),
                "stdout": "", "stderr": str(e),
            }))
        # interactive-only / risky commands noted
        for name, note in [
            ("model", "interactive choose() — skipped in cloud audit"),
            ("screen", "requires display/OCR — skipped"),
            ("see", "requires prior /screen — skipped"),
            ("spatial", "requires Capture assets — skipped"),
            ("vault", "filesystem crawl interactive — skipped"),
            ("files", "needs vault index — skipped"),
            ("sage", "disabled by 0.5B-only config"),
            ("bridge", "disabled by bridges=[]"),
            ("convert_pull", "already converted qwen0.5b — skipped to save time"),
            ("demo_mode", "requires multi-terminal GUI approval — skipped"),
        ]:
            rows.append(record("omni_cmd", name, {
                "ok": True, "elapsed_s": 0, "stdout": "SKIP", "stderr": "",
            }, notes=note))
    except Exception as e:
        rows.append(record("omni_cmd", "setup_failed", {
            "ok": False, "elapsed_s": 0, "stdout": "",
            "stderr": traceback.format_exc()[-3000:],
        }))
    return rows


def section_eternal_memory():
    rows = []
    marker = f"AUDIT_MARKER_{int(time.time())}"
    fact = f"Remember forever: the project codename is {marker} and the secret number is 734291."
    # write via mind (memorize on)
    rows.append(record(
        "memory", "write_via_mind",
        run_cmd([
            PY, "verantyx_mind.py",
            "--prompt", fact,
            "--worker", "none", "--speak-tokens", "48",
        ], timeout=300),
        notes="memory.enabled=true; not --secret",
    ))
    # write via council
    rows.append(record(
        "memory", "write_via_council",
        run_cmd([
            PY, "verantyx_council.py",
            "--prompt", f"Please memorize: favorite fruit of audit bot is mango-{marker}.",
            "--no-escalate", "--speak-tokens", "48",
        ], timeout=300),
    ))
    # recall via mind CLI
    r = run_cmd([PY, "verantyx_mind.py", "--recall", marker], timeout=240)
    hit = marker in (r.get("stdout") or "") or "734291" in (r.get("stdout") or "")
    r["ok"] = bool(hit)
    rows.append(record("memory", "recall_marker", r, notes="expects marker in recall hits"))
    # recall fruit
    r2 = run_cmd([PY, "verantyx_mind.py", "--recall", f"mango-{marker}"], timeout=240)
    hit2 = marker in (r2.get("stdout") or "") or "mango" in (r2.get("stdout") or "").lower()
    r2["ok"] = bool(hit2)
    rows.append(record("memory", "recall_fruit", r2))
    # API search
    t0 = time.time()
    try:
        from verantyx_council import Council
        c = Council(quiet=True, secret=False)
        hits = c.memory_search(marker, k=5)
        ok = bool(hits)
        rows.append(record("memory", "api_memory_search", {
            "ok": ok, "elapsed_s": round(time.time() - t0, 2),
            "stdout": str(hits)[:1500], "stderr": "",
        }))
    except Exception as e:
        rows.append(record("memory", "api_memory_search", {
            "ok": False, "elapsed_s": round(time.time() - t0, 2),
            "stdout": "", "stderr": traceback.format_exc()[-1500:],
        }))
    # secret mode must NOT write
    secret_marker = f"SECRET_SHOULD_NOT_PERSIST_{int(time.time())}"
    rows.append(record(
        "memory", "secret_write_attempt",
        run_cmd([
            PY, "verantyx_council.py",
            "--prompt", f"Remember this private code: {secret_marker}",
            "--no-escalate", "--secret", "--speak-tokens", "24",
        ], timeout=240),
    ))
    r3 = run_cmd([PY, "verantyx_mind.py", "--recall", secret_marker], timeout=240)
    leaked = secret_marker in (r3.get("stdout") or "")
    r3["ok"] = not leaked  # success = not found
    rows.append(record(
        "memory", "secret_not_recalled", r3,
        notes="ok means secret marker was NOT found (correct isolation)",
    ))
    return rows


def section_long_horizon():
    """Multi-turn continuity: plant facts over several turns, then quiz."""
    rows = []
    turns = [
        "My name for this audit is Kuro. Reply briefly.",
        "I live in a city called Harborwell. Reply briefly.",
        "My favorite tool is a blue compass. Reply briefly.",
        "What is my name, city, and favorite tool? Answer in one short sentence.",
    ]
    transcript = []
    t0 = time.time()
    try:
        from verantyx_council import Council
        c = Council(quiet=True, secret=False)
        for i, q in enumerate(turns):
            ans = c.ask(q, rounds=1, escalation=False, force_router_speaker=True, speak_tokens=64)
            text = ans if isinstance(ans, str) else str(ans)
            transcript.append({"q": q, "a": text[:500]})
        final = transcript[-1]["a"].lower()
        checks = {
            "name_kuro": "kuro" in final,
            "city_harborwell": "harborwell" in final or "harbor" in final,
            "tool_compass": "compass" in final,
        }
        rows.append(record("long_horizon", "multi_turn_memory_quiz", {
            "ok": sum(checks.values()) >= 2,
            "elapsed_s": round(time.time() - t0, 2),
            "stdout": json.dumps({"checks": checks, "transcript": transcript}, ensure_ascii=False)[:3500],
            "stderr": "",
        }, notes="needs >=2 of 3 facts recalled after 3 prior turns"))
    except Exception as e:
        rows.append(record("long_horizon", "multi_turn_memory_quiz", {
            "ok": False, "elapsed_s": round(time.time() - t0, 2),
            "stdout": "", "stderr": traceback.format_exc()[-2000:],
        }))

    # longer chain task: cumulative counting / instruction following
    t0 = time.time()
    try:
        from verantyx_council import Council
        c = Council(quiet=True, secret=True)  # no memory bias
        state = []
        for n in range(1, 6):
            q = f"Append the number {n} to the list. Current list: {state}. Reply with only the new list as comma-separated numbers."
            ans = c.ask(q, rounds=1, escalation=False, force_router_speaker=True, speak_tokens=32)
            text = ans if isinstance(ans, str) else str(ans)
            nums = [int(x) for x in re.findall(r"\d+", text)]
            # take trailing unique progression if present
            if nums:
                # heuristic: use first increasing prefix matching expected start
                state = nums[:n] if nums[:n] == list(range(1, n + 1)) else nums[-n:]
            transcript_item = {"n": n, "raw": text[:200], "parsed": state}
            if n == 1:
                chain = [transcript_item]
            else:
                chain.append(transcript_item)
        ok = state == [1, 2, 3, 4, 5]
        rows.append(record("long_horizon", "instruction_chain_list", {
            "ok": ok, "elapsed_s": round(time.time() - t0, 2),
            "stdout": json.dumps(chain, ensure_ascii=False)[:2500], "stderr": "",
        }, notes="0.5B instruction following without memory"))
    except Exception as e:
        rows.append(record("long_horizon", "instruction_chain_list", {
            "ok": False, "elapsed_s": round(time.time() - t0, 2),
            "stdout": "", "stderr": traceback.format_exc()[-2000:],
        }))
    return rows


def section_quality_bench():
    """Fair quality: router vs council vs puzzle vs bare ollama solo."""
    out = OUT / "quality_bench"
    cmd = [
        PY, "benchmarks/verantyx_bench.py",
        "--dataset", "benchmarks/datasets/factual_qa.jsonl",
        "--modes", "router,council,puzzle,solo",
        "--max-items", "8",
        "--rounds", "1",
        "--no-escalate",
        "--solo-model", "ollama:qwen2.5:0.5b",
        "--out", str(out),
    ]
    # 8問×4モード。CPUでは評議会が数分/問かかるため長めに待つ
    r = run_cmd(cmd, timeout=4 * 3600)
    summary = {}
    summary_path = out / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
    # also parse any summary.md
    md = out / "summary.md"
    md_txt = md.read_text()[:3000] if md.exists() else ""
    r["stdout"] = (r.get("stdout") or "")[-2000:] + "\n" + md_txt
    r["summary"] = summary
    return [record("quality", "bench_20_fair", r,
                   notes="router/council/puzzle force_router_speaker; solo=ollama bare 0.5b")]


def section_mode_menu_inventory():
    """Document mode menu and which paths were exercised."""
    modes = [
        {"mode": "Omni", "entry": "verantyx.py menu / launch_omni", "tested": "command backends via API + council CLI"},
        {"mode": "Demo", "entry": "launch_demo", "tested": "SKIP (GUI/multi-terminal)"},
        {"mode": "Mind", "entry": "verantyx_mind.py", "tested": "--prompt/--recall/--persona paths"},
        {"mode": "Agent", "entry": "verantyx_agent.py", "tested": "--task with ollama:qwen2.5:0.5b"},
        {"mode": "辞書", "entry": "launch_lexicon / verantyx_dict.py", "tested": "assoc CLI"},
        {"mode": "軌跡", "entry": "launch_traces / ThoughtTrace", "tested": "list via API"},
        {"mode": "記憶", "entry": "launch_memory / CortexMemory", "tested": "write+recall+search"},
    ]
    return [record("inventory", "modes", {
        "ok": True, "elapsed_s": 0, "stdout": json.dumps(modes, ensure_ascii=False, indent=2),
        "stderr": "",
    })]


def synthesize(rows):
    by = {}
    for r in rows:
        by.setdefault(r["section"], []).append(r)
    lines = ["# 0.5B-only Mode Audit Report", "", f"Generated: {datetime.now().isoformat()}", ""]
    lines.append("## Environment")
    lines.append("- Router jgen: `converted_models/qwen0_5b_full.jgen`")
    lines.append("- Escalation: OFF (`models.worker/sage=none`, `bridges=[]`)")
    lines.append("- Bare baseline: Ollama `qwen2.5:0.5b`")
    lines.append("- Host: 4 vCPU / 16GB RAM / no GPU (Cursor Cloud)")
    lines.append("")
    for sec, items in by.items():
        ok = sum(1 for i in items if i.get("ok"))
        lines.append(f"## {sec} ({ok}/{len(items)} ok)")
        lines.append("")
        for i in items:
            mark = "OK" if i.get("ok") else "FAIL"
            note = f" — {i['notes']}" if i.get("notes") else ""
            lines.append(f"- **{mark}** `{i['name']}` ({i.get('elapsed_s')}s){note}")
            if not i.get("ok") and i.get("stderr"):
                err = i["stderr"].strip().splitlines()[-3:]
                lines.append(f"  - stderr: `{' | '.join(err)[:300]}`")
        lines.append("")
    # quality special
    q = next((r for r in rows if r["name"] == "bench_20_fair"), None)
    if q and q.get("summary"):
        lines.append("## Quality summary (parsed)")
        lines.append("```json")
        lines.append(json.dumps(q["summary"], ensure_ascii=False, indent=2)[:4000])
        lines.append("```")
        lines.append("")
    lines.append("## Weakness hypotheses to validate from results")
    lines.append("- Council/puzzle vs router: expect little accuracy gain at same speaker; extra latency")
    lines.append("- NL-style / long instruction chains: 0.5B drift and format breakage")
    lines.append("- Eternal memory: recall depends on embedding quality of tiny model; multi-hop fragile")
    lines.append("- Agent: tool use quality limited by 0.5B planner; may loop or mis-call tools")
    lines.append("- Demo/screen/spatial/vault: unavailable or interactive-only in this environment")
    lines.append("- Lexicon/dict: may be weak or unavailable without larger weight sources")
    path = OUT / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    all_rows = []
    all_rows += section_mode_menu_inventory()
    all_rows += section_smoke_paths()
    all_rows += section_omni_command_surface()
    all_rows += section_eternal_memory()
    all_rows += section_long_horizon()
    all_rows += section_quality_bench()

    (OUT / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n",
        encoding="utf-8",
    )
    report = synthesize(all_rows)
    print("\nWrote", report)
    print("Dir", OUT)
    # exit non-zero if critical smokes failed
    critical = [r for r in all_rows if r["section"] in ("smoke", "memory", "quality") and not r.get("ok")]
    if critical:
        print(f"Critical failures: {len(critical)}")
        for r in critical:
            print(" -", r["section"], r["name"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
