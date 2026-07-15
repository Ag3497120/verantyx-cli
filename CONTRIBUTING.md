# Contributing to Verantyx

Thanks for considering a contribution. Verantyx is a **local AI harness** — please keep claims honest: structure (routing, vector council, memory) is not world knowledge, and council is not an accuracy booster. Numbers live in [`benchmarks/README.md`](benchmarks/README.md); do not invent higher accuracy in docs or issues.

## Before you start

- [`LICENSE`](LICENSE) — repository **code** is MIT; **model weights are not**
- [`SECURITY.md`](SECURITY.md) — shell/file/web risk, memory dirs, wipe steps, reporting
- [`PRIVACY.md`](PRIVACY.md) — what stays local vs what may leave

## Ways to help

1. **Docs** — typo fixes, clearer Japanese/English, translation polish  
2. **Smoke / scripts** — make onboarding checks more reliable  
3. **Demo assets** — short GIF or command-only demo scripts (no fake metrics)  
4. **Optional packaging** — e.g. Dockerfile (help wanted; not claimed as shipped until merged)

Look for issues labeled **`good first issue`** or **`help wanted`**.

## Good first issues

Search: [good first issue](https://github.com/Ag3497120/verantyx-cli/labels/good%20first%20issue) · [help wanted](https://github.com/Ag3497120/verantyx-cli/labels/help%20wanted)

Typical starters:

- README / QUICKSTART wording / license clarity
- Smoke script robustness
- Demo GIF or script outline
- Add optional Dockerfile (issue may exist before the file does)

## Dev basics

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
# prefer a feature branch off main
git checkout -b fix/your-topic
```

If weights already exist: `python3 verantyx.py` (see [`docs/QUICKSTART.md`](docs/QUICKSTART.md)).  
Full first-time path: `./setup.sh --model` (Rust build is advanced — not required to edit docs).

## Pull requests

- **Prefer small PRs and small commits** going forward (easier review; do not rewrite entire git history to clean up past noise)
- One concern per PR when possible  
- Do not widen accuracy claims; link benches instead  
- For behavior changes, note how you tested (even a short manual Omni check)  
- Docs-only PRs: a short “docs review” checklist is enough  

## Code of conduct (brief)

Be respectful. No discriminatory language in issues, PRs, or docs. Disagreement about design is fine; personal attacks are not.

## Questions

Open a GitHub Discussion or Issue. For claim boundaries, start from [`benchmarks/README.md`](benchmarks/README.md) and [`docs/OMNI_PROFILES.md`](docs/OMNI_PROFILES.md).
