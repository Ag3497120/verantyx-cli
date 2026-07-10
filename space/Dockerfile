# ── Stage 1: Rust 推論エンジン (CPU / candle) ────────────────────────────────
FROM rust:slim AS engine
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY jcross_engine_glm/Cargo.toml ./
COPY jcross_engine_glm/src ./src
RUN cargo build --release --no-default-features --lib

# ── Stage 2: Python ランタイム ───────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=engine /build/target/release/libjcross_engine_glm.so /app/
COPY *.py /app/
COPY static/ /app/static/

ENV JCROSS_LIB=/app/libjcross_engine_glm.so \
    JGEN_MODEL=/app/converted_models/qwen05b_full.jgen \
    JGEN_TOKENIZER=Qwen/Qwen2.5-0.5B-Instruct \
    JCROSS_DEVICE=cpu \
    JCROSS_CACHE_GB=4 \
    HF_HOME=/app/hf_cache \
    PYTHONUNBUFFERED=1

# モデル取得 + JGEN変換 + ウォームアップをイメージに焼き込む (コールドスタート高速化)
RUN python build_model.py && chmod -R a+rwX /app

# HF Spaces は非rootで実行される
RUN useradd -m -u 1000 user
USER user

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
