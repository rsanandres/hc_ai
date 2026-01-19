"""Comprehensive tests for reranker components."""

from __future__ import annotations

import os
import time
import unittest
from pathlib import Path

from dotenv import load_dotenv
import sys

from langchain_core.documents import Document

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

from POC_retrieval.reranker.cache import InMemoryCache, build_cache_key
from POC_retrieval.reranker.cross_encoder import Reranker


class CacheTests(unittest.TestCase):
    def test_cache_key_stable(self) -> None:
        key1 = build_cache_key("Test Query", ["b", "a"])
        key2 = build_cache_key("test query", ["a", "b"])
        self.assertEqual(key1, key2)

    def test_cache_ttl_expiry(self) -> None:
        cache = InMemoryCache(ttl_seconds=1, max_size=10)
        cache.set("key", [("doc", 1.0)])
        self.assertIsNotNone(cache.get("key"))
        time.sleep(1.1)
        self.assertIsNone(cache.get("key"))

    def test_cache_lru_eviction(self) -> None:
        cache = InMemoryCache(ttl_seconds=60, max_size=2)
        cache.set("key1", [("doc1", 1.0)])
        cache.set("key2", [("doc2", 2.0)])
        cache.get("key1")
        cache.set("key3", [("doc3", 3.0)])
        self.assertIsNone(cache.get("key2"))
        self.assertIsNotNone(cache.get("key1"))


class RerankerTests(unittest.TestCase):
    @unittest.skipUnless(os.getenv("RUN_RERANKER_MODEL_TESTS") == "1", "Set RUN_RERANKER_MODEL_TESTS=1 to run")
    def test_reranker_scores(self) -> None:
        reranker = Reranker("sentence-transformers/ms-marco-MiniLM-L-6-v2", device="cpu")
        docs = [Document(page_content="blood pressure measurement"), Document(page_content="recipe for pasta")]
        scores = reranker.score("blood pressure", [doc.page_content for doc in docs])
        self.assertEqual(len(scores), 2)

    @unittest.skipUnless(os.getenv("RUN_RERANKER_MODEL_TESTS") == "1", "Set RUN_RERANKER_MODEL_TESTS=1 to run")
    def test_reranker_rerank(self) -> None:
        reranker = Reranker("sentence-transformers/ms-marco-MiniLM-L-6-v2", device="cpu")
        docs = [
            Document(page_content="blood pressure measurement"),
            Document(page_content="recipe for pasta"),
        ]
        reranked = reranker.rerank("blood pressure", docs, top_k=1)
        self.assertEqual(len(reranked), 1)


if __name__ == "__main__":
    unittest.main()
