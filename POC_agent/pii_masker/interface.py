"""Abstract interface for PII masking implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple


class PIIMaskerInterface(ABC):
    """Interface for PII masking providers."""

    @abstractmethod
    def mask_pii(self, text: str) -> Tuple[str, Dict]:
        """Return masked text and an entity map."""

    @abstractmethod
    def detect_pii(self, text: str) -> List[Dict]:
        """Detect PII entities without masking."""
