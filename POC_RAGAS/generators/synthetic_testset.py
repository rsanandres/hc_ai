"""Synthetic testset generation using RAGAS."""

from __future__ import annotations

import asyncio
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import (
    MultiHopAbstractQuerySynthesizer,
    SingleHopSpecificQuerySynthesizer,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.utils.db_loader import get_distinct_patient_ids, load_documents


@dataclass
class TestsetConfig:
    test_size: int
    simple_ratio: float
    multihop_ratio: float
    conditional_ratio: float
    seed: int = 42


def _ensure_dirs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _build_generator() -> TestsetGenerator:
    if not CONFIG.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for RAGAS testset generation.")
    llm = ChatOpenAI(model=CONFIG.ragas_model, api_key=CONFIG.openai_api_key)
    embedding_model = OpenAIEmbeddings(api_key=CONFIG.openai_api_key)
    return TestsetGenerator.from_langchain(llm, embedding_model=embedding_model)


async def _sample_documents(
    test_size: int,
    patient_ids: Sequence[str] | None = None,
    per_patient_limit: int = 20,
) -> List[Document]:
    if patient_ids is None:
        patient_ids = await get_distinct_patient_ids(limit=max(test_size * 2, 50))

    rng = random.Random(42)
    sampled_patients = rng.sample(list(patient_ids), k=min(len(patient_ids), max(10, test_size // 2)))

    documents: List[Document] = []
    for patient_id in sampled_patients:
        chunks = await load_documents(limit=per_patient_limit, patient_ids=[patient_id])
        documents.extend(chunks)
        if len(documents) >= test_size * 10:
            break
    return documents[: test_size * 10]


def _build_synthesizers(config: TestsetConfig):
    total = config.simple_ratio + config.multihop_ratio + config.conditional_ratio
    if total == 0:
        raise ValueError("At least one question ratio must be > 0.")

    return [
        (SingleHopSpecificQuerySynthesizer(), config.simple_ratio / total),
        (MultiHopAbstractQuerySynthesizer(), config.multihop_ratio / total),
        (MultiHopAbstractQuerySynthesizer(), config.conditional_ratio / total),
    ]


def _serialize_testset(testset, output_path: Path) -> None:
    _ensure_dirs(output_path)
    try:
        dataframe = testset.to_pandas()
        dataframe.to_json(output_path, orient="records", indent=2)
        return
    except Exception:
        pass

    try:
        records = list(testset)
        output_path.write_text(json.dumps(records, indent=2))
    except Exception as exc:
        raise RuntimeError(f"Unable to serialize testset: {exc}") from exc


async def generate_synthetic_testset(
    output_path: Path,
    patient_ids: Iterable[str] | None = None,
    config: TestsetConfig | None = None,
) -> Path:
    config = config or TestsetConfig(
        test_size=CONFIG.test_set_size,
        simple_ratio=CONFIG.question_distribution_simple,
        multihop_ratio=CONFIG.question_distribution_multihop,
        conditional_ratio=CONFIG.question_distribution_conditional,
    )

    documents = await _sample_documents(config.test_size, list(patient_ids) if patient_ids else None)
    if not documents:
        raise RuntimeError("No documents available to generate a testset.")

    generator = _build_generator()
    synthesizers = _build_synthesizers(config)

    testset = await asyncio.to_thread(
        generator.generate_with_langchain_docs,
        documents,
        testset_size=config.test_size,
        query_distribution=synthesizers,
    )

    _serialize_testset(testset, output_path)
    return output_path
