"""Configuration for RAGAS evaluation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from utils.env_loader import load_env_recursive


REPO_ROOT = Path(__file__).resolve().parents[1]
load_env_recursive(REPO_ROOT)


@dataclass(frozen=True)
class RagasConfig:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ragas_model: str = os.getenv("RAGAS_MODEL", "gpt-4o-mini")
    test_set_size: int = int(os.getenv("RAGAS_TEST_SET_SIZE", "120"))
    question_distribution_simple: float = float(os.getenv("RAGAS_Q_SIMPLE", "0.4"))
    question_distribution_multihop: float = float(os.getenv("RAGAS_Q_MULTI", "0.35"))
    question_distribution_conditional: float = float(os.getenv("RAGAS_Q_COND", "0.25"))
    noise_ratio: float = float(os.getenv("RAGAS_NOISE_RATIO", "0.25"))
    noise_seed: int = int(os.getenv("RAGAS_NOISE_SEED", "42"))

    data_dir: Path = Path(os.getenv("RAGAS_DATA_DIR", REPO_ROOT / "data" / "fhir"))
    testset_dir: Path = Path(os.getenv("RAGAS_TESTSET_DIR", Path(__file__).resolve().parent / "data" / "testsets"))
    results_dir: Path = Path(os.getenv("RAGAS_RESULTS_DIR", Path(__file__).resolve().parent / "data" / "results"))
    checkpoint_dir: Path = Path(os.getenv("RAGAS_CHECKPOINT_DIR", Path(__file__).resolve().parent / "data" / "checkpoints"))
    checkpoint_interval: int = int(os.getenv("RAGAS_CHECKPOINT_INTERVAL", "10"))

    reranker_url: str = os.getenv("RERANKER_SERVICE_URL", "http://localhost:8000/retrieval")
    agent_api_url: str = os.getenv("AGENT_API_URL", "http://localhost:8000/agent/query")

    db_user: str | None = os.getenv("DB_USER")
    db_password: str | None = os.getenv("DB_PASSWORD")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: str = os.getenv("DB_PORT", "5432")
    db_name: str | None = os.getenv("DB_NAME")

    include_full_json: bool = os.getenv("RAGAS_INCLUDE_FULL_JSON", "true").lower() in {"1", "true", "yes"}


CONFIG = RagasConfig()
