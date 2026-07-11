# Verantyx

**Languages:** [日本語](README.md) · [English](README-en.md) · [简体中文](README-zh-CN.md) · [繁體中文](README-zh-TW.md) · [한국어](README-ko.md) · [Español](README-es.md) · [Português](README-pt-BR.md) · [Deutsch](README-de.md) · [Français](README-fr.md) · [Русский](README-ru.md) · [Українська](README-uk.md) · [Türkçe](README-tr.md) · [العربية](README-ar.md)

## Français

**Runtime IA local résident / couche de contrôle**

Verantyx **ne** rivalise **pas** sur les « modèles plus intelligents » : c’est un CLI sur votre machine qui contrôle **qui appeler, quand mémoriser, comment porter le consensus en vecteurs**. Docs : [日本語](README.md) / [English](README-en.md).

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

