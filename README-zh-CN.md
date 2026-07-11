# Verantyx

**Languages:** [日本語](README.md) · [English](README-en.md) · [简体中文](README-zh-CN.md) · [繁體中文](README-zh-TW.md) · [한국어](README-ko.md) · [Español](README-es.md) · [Português](README-pt-BR.md) · [Deutsch](README-de.md) · [Français](README-fr.md) · [Русский](README-ru.md) · [Українська](README-uk.md) · [Türkçe](README-tr.md) · [العربية](README-ar.md)

## 简体中文

**本地常驻 AI 运行时 / 控制层**

Verantyx **不是**比拼「更聪明模型」的产品，而是在你机器上控制「调用谁、何时记忆、如何用向量达成共识」的 CLI。完整说明见 [日本語](README.md) / [English](README-en.md)。

---

## Benchmark snapshot (same numbers everywhere)

| Fair 501 (same 0.5B speaker) | Accuracy |
|---|---|
| router | 52.5% |
| vector council | 52.3% |

| Medium (NL vs vector, 85 items) | Accuracy | Avg time |
|---|---|---|
| router | 60.0% | 7.0s |
| vector council | **63.5%** | 8.8s |
| NL council | 48.2% | 19.7s |

→ Accuracy ≈ speaker choice. Vectors beat NL debate as a medium. Details: [benchmarks/README.md](benchmarks/README.md)

---

## Quick start

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli && ./setup.sh --model
source .venv/bin/activate && python verantyx.py
```

