# Codec Round-Trip Report (Phase 1)

Phase 1 measures final-layer half-codec only (dist_from_vector / encode_soft). Not a full English↔hidden codec; not intermediate layers; not lossless reconstruction.

- n = 5
- mean round-trip cosine: **0.844**
- mean baseline cosine: **0.840**
- soft improves over baseline: **100.0%**
- Write keyword retention: **60.0%** (Wilson 23.1–88.2)

```bash
python3 benchmarks/codec_roundtrip.py --max-items 5 --out benchmarks/results/codec_p1_smoke
```
