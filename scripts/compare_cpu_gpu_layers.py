#!/usr/bin/env python3
"""Compare the CPU and Metal forward paths numerically.

Comparing generated text tells you *that* the GPU path is wrong, not *where*.

IMPORTANT — which FFI to use. `jcross_engine_encode_layers` looks like the
right tool (it dumps every layer) but `execute_worker_forward_layers` never
consults `gpu_enabled()`, so it runs on CPU regardless of
`JCROSS_HYBRID_GPU`. Pointing this script at it compares CPU against CPU and
prints a perfect match — which is exactly what happened on the first run, and
the giveaway was `max|Δ| = 0.000000` on every layer: agreement between two
paths is never bit-exact, only identical code is.

Only two entry points actually branch on `gpu_enabled()`:
`execute_worker_forward_soft` (= `jcross_engine_encode`) and
`execute_generation_loop` (= `jcross_engine_generate`). So `encode` is the
comparison that means something; it yields one final vector rather than a
per-layer trace, so it answers "does the GPU path diverge" but not yet
"at which layer".

Device selection is read once at engine creation, so each path needs its own
process. Run:

    python3 scripts/compare_cpu_gpu_layers.py dump <model.jgen> cpu  out_cpu.npy
    python3 scripts/compare_cpu_gpu_layers.py dump <model.jgen> gpu  out_gpu.npy
    python3 scripts/compare_cpu_gpu_layers.py diff out_cpu.npy out_gpu.npy

`run` does all three in one go.
"""
from __future__ import annotations

import array
import ctypes
import json
import math
import os
import subprocess
import sys

# Deliberately stdlib-only: this has to run on whatever machine holds the
# model, and the verification machine had no numpy.


def find_dylib() -> str:
    env = os.environ.get("JCROSS_ENGINE_DYLIB")
    if env and os.path.exists(env):
        return env
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for p in [
        os.path.join(root, "jcross_engine_glm/target/release/libjcross_engine_glm.dylib"),
        os.path.expanduser("~/verantyx/cli/VerantyxIDE/Vendor/libjcross_engine_glm.dylib"),
        os.path.expanduser(
            "~/Projects/verantyx-check/cli/VerantyxIDE/Vendor/libjcross_engine_glm.dylib"
        ),
    ]:
        if os.path.exists(p):
            return p
    raise SystemExit("libjcross_engine_glm.dylib not found (set JCROSS_ENGINE_DYLIB)")


def load_engine(lib, path: str):
    lib.jcross_engine_create.restype = ctypes.c_void_p
    lib.jcross_engine_create.argtypes = [ctypes.c_char_p]
    lib.jcross_engine_hidden_dim.restype = ctypes.c_int32
    lib.jcross_engine_hidden_dim.argtypes = [ctypes.c_void_p]
    lib.jcross_engine_num_layers.restype = ctypes.c_int32
    lib.jcross_engine_num_layers.argtypes = [ctypes.c_void_p]
    # encode (NOT encode_layers) is the one that honours gpu_enabled().
    lib.jcross_engine_encode.restype = ctypes.c_int32
    lib.jcross_engine_encode.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
    ]
    lib.jcross_engine_topk_distribution.restype = ctypes.c_int32
    lib.jcross_engine_topk_distribution.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    eng = lib.jcross_engine_create(path.encode())
    if not eng:
        raise SystemExit(f"engine refused to load: {path}")
    return eng


def dump(model: str, mode: str, out_path: str) -> None:
    # Must be set before the engine is created — the device decision is made there.
    if mode == "cpu":
        os.environ["JCROSS_HYBRID_GPU"] = "0"
    elif mode == "gpu":
        os.environ["JCROSS_HYBRID_GPU"] = "1"
        os.environ["JCROSS_GPU"] = "1"
    else:
        raise SystemExit("mode must be cpu|gpu")

    lib = ctypes.CDLL(find_dylib())
    eng = load_engine(lib, model)
    hidden = lib.jcross_engine_hidden_dim(eng)
    n_layers = lib.jcross_engine_num_layers(eng)

    # A fixed, arbitrary token sequence: the comparison only needs both paths
    # to see identical input, not meaningful text.
    tokens = [1, 2, 3, 4, 5, 6, 7, 8]
    layers = [n_layers]  # single final hidden state

    tok_arr = (ctypes.c_uint32 * len(tokens))(*tokens)
    out = (ctypes.c_float * hidden)()

    rc = lib.jcross_engine_encode(eng, tok_arr, len(tokens), out, hidden)
    if rc < 0:
        raise SystemExit(f"encode failed rc={rc} (mode={mode})")

    vals = array.array("f", out)
    with open(out_path, "wb") as f:
        vals.tofile(f)
    meta = {"hidden": hidden, "n_layers": n_layers, "mode": mode, "layers": layers}
    with open(out_path + ".json", "w") as f:
        json.dump(meta, f)
    print(f"[{mode}] wrote final hidden state ({hidden}) -> {out_path}")


def load_rows(path: str, hidden: int):
    vals = array.array("f")
    with open(path, "rb") as f:
        vals.fromfile(f, os.path.getsize(path) // 4)
    return [vals[i * hidden:(i + 1) * hidden] for i in range(len(vals) // hidden)]


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-9 or nb < 1e-9:
        return float("nan")
    return dot / (na * nb)


def diff(cpu_path: str, gpu_path: str, threshold: float = 0.999) -> int:
    meta = json.load(open(cpu_path + ".json"))
    hidden = meta["hidden"]
    cpu = load_rows(cpu_path, hidden)
    gpu = load_rows(gpu_path, hidden)
    layer_types = meta.get("layer_types")

    print(f"{'layer':>6}  {'cosine':>10}  {'max|Δ|':>12}   verdict")
    first_bad = None
    for i in range(min(len(cpu), len(gpu))):
        c = cosine(cpu[i], gpu[i])
        d = max(abs(x - y) for x, y in zip(cpu[i], gpu[i]))
        ok = (c == c) and c >= threshold  # c != c catches NaN
        if not ok and first_bad is None:
            first_bad = i
        tag = "" if ok else "  <-- DIVERGES"
        label = f"{i}" if i < meta["n_layers"] else "final-norm"
        if layer_types and i < len(layer_types):
            label += f" ({layer_types[i]})"
        print(f"{label:>6}  {c:10.6f}  {d:12.6f}{tag}")

    print()
    if first_bad is None:
        print(f"MATCH — every layer within cosine >= {threshold}")
        return 0
    print(f"DIVERGES at row {first_bad} — the Metal path is not numerically equivalent")
    return 1


def logits(model: str, cpu_path: str, gpu_path: str, k: int = 8) -> int:
    """Score both hidden states through the *same* lm_head.

    `execute_topk_distribution` never consults `gpu_enabled()`, so running it
    on each dumped vector isolates one question: is the encode residual large
    enough to change which token wins? Same weights, same code, only the input
    differs — so any difference in the ranking is caused by the residual and
    nothing else.
    """
    meta = json.load(open(cpu_path + ".json"))
    hidden = meta["hidden"]

    lib = ctypes.CDLL(find_dylib())
    eng = load_engine(lib, model)

    def topk(vec):
        arr = (ctypes.c_float * hidden)(*vec)
        ids = (ctypes.c_uint32 * k)()
        probs = (ctypes.c_float * k)()
        n = ctypes.c_size_t(0)
        rc = lib.jcross_engine_topk_distribution(
            eng, b"lm_head", arr, hidden, k, ids, probs, ctypes.byref(n)
        )
        if rc < 0:
            raise SystemExit(f"topk failed rc={rc}")
        return [(ids[i], probs[i]) for i in range(n.value)]

    cpu_vec = load_rows(cpu_path, hidden)[0]
    gpu_vec = load_rows(gpu_path, hidden)[0]
    c = topk(cpu_vec)
    g = topk(gpu_vec)

    print(f"{'rank':>4}  {'CPU token':>10} {'p':>10}   {'GPU token':>10} {'p':>10}   same")
    for i in range(min(len(c), len(g))):
        same = "yes" if c[i][0] == g[i][0] else "NO"
        print(f"{i:>4}  {c[i][0]:>10} {c[i][1]:10.6f}   {g[i][0]:>10} {g[i][1]:10.6f}   {same}")

    print()
    if not c or not g:
        print("no distribution returned")
        return 1
    if c[0][0] == g[0][0]:
        print(f"ARGMAX AGREES (token {c[0][0]}) — the residual does not change the chosen token.")
        margin = c[0][1] - (c[1][1] if len(c) > 1 else 0.0)
        print(f"top-1 margin on CPU: {margin:.6f}")
        print("Generation still diverging with a matching argmax points at the")
        print("decode loop (KV cache) rather than the layer maths.")
        return 0
    print(f"ARGMAX DIFFERS: CPU picks {c[0][0]}, GPU picks {g[0][0]}")
    margin = abs(c[0][1] - c[1][1]) if len(c) > 1 else float("nan")
    print(f"top-1/top-2 margin on CPU: {margin:.6f}")
    print("A margin this small means greedy decoding amplifies the encode")
    print("residual: one flipped pick and every later token differs.")
    return 1


def gen(model: str, mode: str, n: int = 6) -> int:
    """Generate `n` tokens and print the ids.

    Narrows where generation diverges. `encode` already matches at cosine
    0.999997 and the first-token top-8 logits are identical, but that came
    from `execute_worker_forward_soft`; generation runs a *different* entry
    point with its own prefill. Comparing the first few generated ids says
    whether that prefill is already wrong (token 0 differs) or whether the
    recurrent GDN state drifts over steps (token 0 matches, a later one does
    not).
    """
    if mode == "cpu":
        os.environ["JCROSS_HYBRID_GPU"] = "0"
    else:
        os.environ["JCROSS_HYBRID_GPU"] = "1"
        os.environ["JCROSS_GPU"] = "1"

    lib = ctypes.CDLL(find_dylib())
    lib.jcross_engine_generate.restype = ctypes.c_int32
    lib.jcross_engine_generate.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
    ]
    eng = load_engine(lib, model)

    prompt = [1, 2, 3, 4, 5, 6, 7, 8]
    p_arr = (ctypes.c_uint32 * len(prompt))(*prompt)
    out = (ctypes.c_uint32 * n)()
    produced = lib.jcross_engine_generate(eng, p_arr, len(prompt), n, out, n)
    if produced < 0:
        raise SystemExit(f"generate failed rc={produced}")
    ids = [out[i] for i in range(produced)]
    print(f"[{mode}] tokens: {ids}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "dump":
        dump(sys.argv[2], sys.argv[3], sys.argv[4])
        return 0
    if cmd == "diff":
        return diff(sys.argv[2], sys.argv[3])
    if cmd == "gen":
        return gen(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    if cmd == "logits":
        tmp = os.environ.get("TMPDIR", "/tmp")
        return logits(
            sys.argv[2],
            os.path.join(tmp, "layers_cpu.f32"),
            os.path.join(tmp, "layers_gpu.f32"),
        )
    if cmd == "run":
        model = sys.argv[2]
        tmp = os.environ.get("TMPDIR", "/tmp")
        cpu_out = os.path.join(tmp, "layers_cpu.f32")
        gpu_out = os.path.join(tmp, "layers_gpu.f32")
        me = os.path.abspath(__file__)
        for mode, out in (("cpu", cpu_out), ("gpu", gpu_out)):
            subprocess.run(
                [sys.executable, me, "dump", model, mode, out], check=True
            )
        return diff(cpu_out, gpu_out)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
