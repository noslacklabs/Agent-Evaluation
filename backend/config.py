from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


SERVICE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVICE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

DATA_DIR = Path(os.getenv("EVALUATOR_DATA_DIR", SERVICE_DIR / "data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
PACKAGE_DIR = DATA_DIR / "packages"
DB_PATH = Path(os.getenv("EVALUATOR_DB_PATH", DATA_DIR / "evaluator.db")).resolve()

MAX_UPLOAD_BYTES = int(os.getenv("EVALUATOR_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
AGENT_TIMEOUT_SECONDS = float(os.getenv("EVALUATOR_AGENT_TIMEOUT_SECONDS", "90"))
PYTHON_AGENT_TIMEOUT_SECONDS = float(os.getenv("EVALUATOR_PYTHON_TIMEOUT_SECONDS", "120"))
DEEPEVAL_JUDGE_MODEL = os.getenv("DEEPEVAL_JUDGE_MODEL", "gpt-5.4")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


def ensure_directories() -> None:
    for path in (DATA_DIR, UPLOAD_DIR, PACKAGE_DIR):
        path.mkdir(parents=True, exist_ok=True)
