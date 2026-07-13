# LongMemEval Codec A/B (Phase 5)

A/B compares evidence delivery (full prompt text vs Write-codec soft+digest). Not a LongMemEval leaderboard claim; grading is containment heuristic. Separate from Phase 1–4 reconstruction metrics.

| path | accuracy | Wilson 95% | p50 s |
|---|---:|---|---:|
| prompt (A) | 0.0% | (0.0, 0.7934567085261071) | 2.29 |
| codec Write (B) | 0.0% | (0.0, 0.7934567085261071) | 1.20 |

- Δ (codec − prompt): **+0.0pt**
- mean Write cosine (B): 0.8145158005307178

```bash
python3 benchmarks/longmemeval_codec_ab.py --split oracle --max-items 1 --out benchmarks/results/codec_ab_smoke
```
