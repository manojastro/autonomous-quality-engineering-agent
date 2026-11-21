"""Central configuration and path constants."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_APP_DIR = PROJECT_ROOT / "sample_app"
TESTS_SUITE_DIR = PROJECT_ROOT / "tests_suite"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"

ALLOW_THRESHOLD = 85.0
REVIEW_THRESHOLD = 60.0

CONFIDENCE_WEIGHTS = {
    "passed_results": 35.0,
    "changed_module_coverage": 20.0,
    "critical_path_validation": 15.0,
    "unresolved_failures_penalty": 25.0,
    "flakiness_penalty": 10.0,
    "security_findings_penalty": 10.0,
}

MIN_FLAKY_SELECT_SCORE = 0.3
RETRY_ONCE_SUSPECT_FLAKY = True
RUNNER_TIMEOUT_S = 240


def default_db_url() -> str:
    return os.environ.get("QE_DB_URL", f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}")


@dataclass
class Settings:
    db_url: str = field(default_factory=default_db_url)
    llm_mode: str = field(default_factory=lambda: os.environ.get("LLM_MODE", "mock"))
    llm_api_key: str = field(default_factory=lambda: os.environ.get("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "gpt-4o-mini"))
    runner_timeout_s: int = RUNNER_TIMEOUT_S
    allow_threshold: float = ALLOW_THRESHOLD
    review_threshold: float = REVIEW_THRESHOLD


def get_settings() -> Settings:
    return Settings()
