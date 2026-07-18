# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
yuna doctor   # checks every external dependency and service
```

## Development

- Lint/format: `ruff check src tests` and `ruff format src tests`
- Tests: `pytest` — the suite covers the pure logic modules and runs without
  a GPU, Ollama, or any external service. Put new pure logic (parsers,
  thresholds, mappings) in its own module so it stays testable.
- Configuration goes in `config.yaml` / `src/yuna/core/config.py`, never as
  scattered constants. Secrets go in `.env`.
- Diagnostics go through `yuna.core.logging` (`get_logger(...)`); never add
  a silent `except: pass`.

## Personas and voices

`persona/` and `voice_reference/voices.json` are private and gitignored.
Update `persona.example/` / `voices.example.json` when the expected format
changes. Only add voice references you have the right to clone.

## Pull requests

Keep PRs focused on one change. CI (ruff + pytest) must pass.
