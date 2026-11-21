# Autonomous Quality Engineering Agent

Given a code change, selects the **minimum set of high-value tests**, runs them, separates real failures
from flaky ones, performs evidence-based root-cause analysis and produces a **release-confidence gate** decision.

> Portfolio/POC build. It analyses a bundled `sample_app/` (auth, customers, orders, payments, reports,
> search, admin) with its own test suite in `tests_suite/`.

## What it does

- **Impact analysis**: AST/dependency graph of the code under test (`backend/app/analysis/ast_graph.py`, `impact.py`).
- **Risk + selection**: ranks tests by change risk and picks a minimal high-value subset (`risk.py`, `selection.py`).
- **Run + classify**: executes tests (`services/runner.py`) and classifies flaky vs real failures (`flaky_classifier.py`).
- **RCA**: evidence-based root-cause logic (`rca_logic.py`).
- **Confidence + gate**: confidence math and gate rules decide release readiness (`confidence_math.py`, `gate_rules.py`).
- **API**: changes, tests, bugs, gates and KPI endpoints, plus `/dashboard`, `/health`, `/readiness`, `/metrics`.
- **Evaluation**: `scripts/evaluate.py` measures selection quality, reduction, bug detection, flakiness handling
  and confidence agreement. `scripts/create_regression.py` seeds a regression to test against.

LLM use is optional (`LLM_MODE=mock` by default; OpenAI-compatible via `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`).

## Run

```bash
pip install -e ".[graph]"
python scripts/evaluate.py
uvicorn backend.app.main:app --reload
pytest          # backend/tests (agents, selection, flaky, confidence, gate, runner, workflow, API)
                # and tests_suite (the sample app's own tests)
```

A small `data/wfdebug.db` SQLite file from development is included.
