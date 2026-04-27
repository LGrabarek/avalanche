# Avalanche

A browser-based reproduction of **I.Q.: Intelligent Qube** (1997 PlayStation puzzle game), built entirely in Python with Pygame CE + Pygbag and shipped as a PWA.

## Run it locally

```bash
bash run_dev.sh
# → open http://localhost:8000 (first load ~30s while pygbag fetches CPython)
```

## Repo layout

- `main.py`, `constants.py`, `renderer.py`, `cube_data.py` — game source
- `run_dev.sh`, `pygbag.ini`, `pyproject.toml` — build/dev tooling
- `docs/` — `PLAN.md` (11-step implementation plan), `PROGRESS.md` (step tracker + session log), `STEP<N>_REVIEW.md` (per-step review docs)
- `Research/` — authoritative reference on I.Q. mechanics and scoring
- `CLAUDE.md` + `.claude/memory/` — project instructions for the Claude coding agent
