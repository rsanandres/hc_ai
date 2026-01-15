"""In-memory cache with TTL + LRU eviction for reranking scores."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


def build_cache_key(query: str, document_ids: Iterable[str]) -> str:
    """Build a stable cache key for a query and document IDs."""
    normalized_query = query.strip().lower()
    sorted_ids = sorted(document_ids)
    payload = {"query": normalized_query, "doc_ids": sorted_ids}
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InMemoryCache:
    """Thread-safe in-memory cache with TTL + LRU eviction."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 10000) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._lock = threading.Lock()
        self._store: "OrderedDict[str, Tuple[float, List[Tuple[str, float]]]]" = OrderedDict()
        self._stats = CacheStats()

    def get(self, key: str) -> Optional[List[Tuple[str, float]]]:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self._stats.misses += 1
                return None
            expires_at, value = entry
            if expires_at <= now:
                self._store.pop(key, None)
                self._stats.misses += 1
                return None
            # Refresh LRU order
            self._store.move_to_end(key)
            self._stats.hits += 1
            return value

    def set(self, key: str, value: List[Tuple[str, float]]) -> None:
        if self._ttl_seconds <= 0 or self._max_size <= 0:
            return
        expires_at = time.monotonic() + self._ttl_seconds
        with self._lock:
            self._purge_expired(now=time.monotonic())
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (expires_at, list(value))
            self._evict_if_needed()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "size": len(self._store),
            }

    def _evict_if_needed(self) -> None:
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def _purge_expired(self, now: float) -> None:
        expired_keys = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        for key in expired_keys:
            self._store.pop(key, None)
