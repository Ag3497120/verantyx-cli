# Verantyx — zero-weight demo (keyword classify smoke, no model download)
FROM python:3.11-slim

WORKDIR /app

COPY scripts/smoke_router_classify.py /app/scripts/smoke_router_classify.py
COPY intent_router.py /app/intent_router.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python3", "scripts/smoke_router_classify.py", "--no-model"]
