#!/usr/bin/env python3
"""
jgen_drift_check.py — JGEN変換 (フルランクSVD f16) の重み再構成誤差を検証する
================================================================================
主張の検証: 「SVDロスレス変換」は本当に情報を保持しているか？
jcross_engine_glm の execute_svd_projection は
    y = U @ C_valve @ diag(S) @ V^T @ diag(mod_x) + mod_y
を計算する。変換直後は mod_x=1, mod_y=0, C_valve=I なので、有効な重みは
    W_eff = U @ diag(S) @ V^T
に一致するはずである (lib.rs の該当箇所参照)。

このスクリプトは、変換元の safetensors (BF16, torch不要) の元の重みと、
.jgen ファイルから読んだ U/S/V を再構成した W_eff を直接比較し、
  - 相対フロベニウスノルム誤差 ‖W_eff - W_orig‖_F / ‖W_orig‖_F
  - 最大絶対誤差
  - 出力ベクトルのコサイン類似度 (ランダム入力を通した時の y の一致度)
を測る。これは torch や Rust エンジンを起動せずに実行できる (numpy only)。

使い方:
  python benchmarks/jgen_drift_check.py \\
      --safetensors ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B-Instruct/snapshots/<hash> \\
      --jgen converted_models/qwen2.5-0.5b-worker_full.jgen \\
      --max-layers 8
"""
import argparse
import glob
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ── safetensors (BF16) を torch 無しで読む ──────────────────────────────────
def bf16_to_f32(raw_u16):
    """BF16 = fp32 の上位16bitそのもの。左シフトするだけで fp32 に復元できる。"""
    u32 = raw_u16.astype(np.uint32) << 16
    return u32.view(np.float32)


def load_safetensors_dir(model_dir):
    """dict: tensor名 -> np.float32 array。torch/safetensors ライブラリ不要。"""
    files = sorted(glob.glob(os.path.join(model_dir, "*.safetensors")))
    if not files:
        raise FileNotFoundError(f"safetensors が見つかりません: {model_dir}")
    tensors = {}
    for path in files:
        with open(path, "rb") as f:
            (n,) = struct.unpack("<Q", f.read(8))
            header = json.loads(f.read(n))
            base = 8 + n
            for name, meta in header.items():
                if name == "__metadata__":
                    continue
                dtype = meta["dtype"]
                shape = tuple(meta["shape"])
                start, end = meta["data_offsets"]
                f.seek(base + start)
                raw = f.read(end - start)
                if dtype == "BF16":
                    arr = bf16_to_f32(np.frombuffer(raw, dtype=np.uint16)).reshape(shape)
                elif dtype == "F16":
                    arr = np.frombuffer(raw, dtype=np.float16).astype(np.float32).reshape(shape)
                elif dtype == "F32":
                    arr = np.frombuffer(raw, dtype=np.float32).reshape(shape)
                else:
                    continue  # 整数量子化等は本検証の対象外
                tensors[name] = arr
    return tensors


# ── JGEN v3 の SVD テンソルを読む ────────────────────────────────────────────
def iter_jgen_svd_tensors(jgen_path):
    """JGEN v3 をストリームで読み、SVDLossless (type=1) テンソルだけを
    (name, U, S, V, mod_x, mod_y, c_valve) として順に yield する。"""
    with open(jgen_path, "rb") as f:
        magic = f.read(4)
        assert magic == b"JGEN", "not a JGEN file"
        _version, count = struct.unpack("<II", f.read(8))
        for _ in range(count):
            (nl,) = struct.unpack("<H", f.read(2))
            name = f.read(nl).decode()
            t = f.read(1)[0]
            if t == 1:
                rows, cols, rank = struct.unpack("<III", f.read(12))
                u = np.frombuffer(f.read(rows * rank * 2), dtype=np.float16).reshape(rows, rank)
                s = np.frombuffer(f.read(rank * 2), dtype=np.float16)
                v = np.frombuffer(f.read(cols * rank * 2), dtype=np.float16).reshape(cols, rank)
                mod_x = np.frombuffer(f.read(cols * 2), dtype=np.float16)
                mod_y = np.frombuffer(f.read(rows * 2), dtype=np.float16)
                c_valve = np.frombuffer(f.read(rank * rank * 2), dtype=np.float16).reshape(rank, rank)
                yield name, (u.astype(np.float32), s.astype(np.float32),
                             v.astype(np.float32), mod_x.astype(np.float32),
                             mod_y.astype(np.float32), c_valve.astype(np.float32))
            elif t == 2:
                rows, cols = struct.unpack("<II", f.read(8))
                f.seek(rows * cols * 2, 1)
            elif t == 3:
                (length,) = struct.unpack("<I", f.read(4))
                f.seek(length * 2, 1)
            else:
                break


def reconstruct(u, s, v, mod_x, mod_y, c_valve):
    """execute_svd_projection と同じ経路で重み行列を再構成する。
    y = U @ C @ diag(S) @ V^T @ diag(mod_x) + mod_y  (バイアスは別枠で報告)
    W_eff = U @ C @ diag(S) @ V^T @ diag(mod_x)  (行=out, 列=in を想定)"""
    core = u @ c_valve @ np.diag(s) @ v.T
    w_eff = core * mod_x[None, :]  # 列方向 (入力側) スケール
    return w_eff, mod_y


def hf_name_to_jgen(name):
    """jgen_forge の命名規則に合わせて HF テンソル名を jgen 側の名前に変換。
    layers.N.xxx -> layer.N.xxx  (lib.rs の実装に合わせて調整が必要な場合あり)。"""
    return name


def main():
    ap = argparse.ArgumentParser(description="JGEN SVD 変換の重み再構成誤差を検証")
    ap.add_argument("--safetensors", required=True, help="元モデルの safetensors ディレクトリ")
    ap.add_argument("--jgen", required=True, help="変換後の .jgen ファイル")
    ap.add_argument("--layers", default="", help="比較する層番号 (例 '0,5,12,23')。"
                    "省略時はモデルの層数から自動で先頭/中間/末尾を選ぶ")
    ap.add_argument("--out", default="", help="結果 JSON の出力先")
    a = ap.parse_args()

    print(f"[drift] 元モデル読み込み中 (torch不要, BF16→FP32手動変換): {a.safetensors}")
    hf_tensors = load_safetensors_dir(a.safetensors)
    print(f"[drift] {len(hf_tensors)} テンソルを読み込み")

    linear_suffixes = (".q_proj.weight", ".k_proj.weight", ".v_proj.weight", ".o_proj.weight",
                       ".gate_proj.weight", ".up_proj.weight", ".down_proj.weight")
    hf_linear = {k: v for k, v in hf_tensors.items()
                if k.endswith(linear_suffixes) and ".layers." in k}
    n_layers = 1 + max(int(k.split(".layers.")[1].split(".")[0]) for k in hf_linear)
    print(f"[drift] 元モデルの線形層候補: {len(hf_linear)} 枚 ({n_layers} layers)")

    if a.layers:
        target_layers = sorted({int(x) for x in a.layers.split(",")})
    else:
        target_layers = sorted({0, n_layers // 2, n_layers - 1, min(3, n_layers - 1)})
    target_names = {k for k in hf_linear
                    if int(k.split(".layers.")[1].split(".")[0]) in target_layers}
    print(f"[drift] 検証対象レイヤ: {target_layers} ({len(target_names)} テンソル)")

    print(f"[drift] JGENファイル読み込み中 (対象テンソルのみキャッシュ): {a.jgen}")
    jgen_svd = {}
    for name, mats in iter_jgen_svd_tensors(a.jgen):
        if name in target_names:
            jgen_svd[name] = mats
        if len(jgen_svd) >= len(target_names):
            break
    print(f"[drift] JGEN側で一致したSVDテンソル: {len(jgen_svd)} / {len(target_names)}")

    results = []
    for hf_name in sorted(target_names):
        w_orig = hf_linear[hf_name]
        cand = hf_name if hf_name in jgen_svd else next(
            (jn for jn in jgen_svd if jn.endswith(hf_name) or hf_name.endswith(jn)), None)
        if cand is None:
            print(f"  [skip] {hf_name}: JGEN側に見つかりません")
            continue
        u, s, v, mod_x, mod_y, c_valve = jgen_svd[cand]
        if u.shape[0] != w_orig.shape[0] or v.shape[0] != w_orig.shape[1]:
            print(f"  [skip] {hf_name}: 形状不一致 {u.shape[0], v.shape[0]} vs {w_orig.shape}")
            continue
        w_eff, bias = reconstruct(u, s, v, mod_x, mod_y, c_valve)
        diff = w_eff - w_orig
        rel_fro = float(np.linalg.norm(diff) / (np.linalg.norm(w_orig) + 1e-12))
        max_abs = float(np.max(np.abs(diff)))
        # ランダム入力を通した出力の一致度 (実運用に近い指標)
        rng = np.random.default_rng(0)
        x = rng.standard_normal(w_orig.shape[1]).astype(np.float32)
        y_orig = w_orig @ x
        y_eff = w_eff @ x + bias
        cos = float((y_orig @ y_eff) / (np.linalg.norm(y_orig) * np.linalg.norm(y_eff) + 1e-12))
        results.append({
            "hf_tensor": hf_name, "jgen_tensor": cand, "shape": list(w_orig.shape),
            "rel_frobenius_error": round(rel_fro, 6),
            "max_abs_error": round(max_abs, 6),
            "output_cosine_sim": round(cos, 6),
        })
        print(f"  [{len(results)}/{len(target_names)}] {hf_name}  "
              f"rel_fro={rel_fro:.5f}  cos={cos:.6f}")

    if not results:
        print("[drift] 一致するテンソルが見つかりませんでした。命名規則を確認してください。")
        sys.exit(1)

    rel_errs = [r["rel_frobenius_error"] for r in results]
    coses = [r["output_cosine_sim"] for r in results]
    summary = {
        "n_compared": len(results),
        "rel_frobenius_error_mean": round(float(np.mean(rel_errs)), 6),
        "rel_frobenius_error_max": round(float(np.max(rel_errs)), 6),
        "output_cosine_sim_mean": round(float(np.mean(coses)), 6),
        "output_cosine_sim_min": round(float(np.min(coses)), 6),
        "verdict": (
            "PASS (fp16 SVD再構成は数値的にロスレスに近い)"
            if float(np.mean(rel_errs)) < 0.01 and float(np.min(coses)) > 0.999
            else "WARN (誤差が想定 (fp16量子化) より大きい。要調査)"
        ),
    }
    print("\n[drift] ── 集計 ──")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out_path = a.out or os.path.join(ROOT, "benchmarks", "results", "jgen_drift_check.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "layers": results}, f, ensure_ascii=False, indent=2)
    print(f"\n[drift] 結果を保存: {out_path}")


if __name__ == "__main__":
    main()
