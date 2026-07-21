# Verantyx

**Small router always on. Larger models only when needed. Memory survives restarts.**

Verantyx is a local AI operations harness. It controls which model is called, when memory is written, and how internal agreement is handled. The router stays local; larger speaker models are called only when needed.

## 60-second demo (no model weights required)

~~~bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 scripts/smoke_router_classify.py --no-model
~~~

This smoke test checks routing only; it does not measure answer accuracy.

## Full quickstart

With router weights available, start the CLI with:

~~~bash
source .venv/bin/activate
python3 verantyx.py
~~~

For first-time setup and the weight conversion path, see [docs/QUICKSTART.md](docs/QUICKSTART.md).

## Honest boundaries

Routing, memory, and council are control structures; they are not world knowledge or an accuracy booster. See [benchmarks/README.md](benchmarks/README.md) for measured results and limits.

## Documentation

- [Quickstart](docs/QUICKSTART.md)
- [Japanese guide](README.ja.md)
- [Omni profiles](docs/OMNI_PROFILES.md)
- [Demo](docs/DEMO.md)
- [Contributing](CONTRIBUTING.md)
