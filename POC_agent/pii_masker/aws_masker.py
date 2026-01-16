"""AWS Comprehend Medical PII masking implementation (future)."""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import boto3

from .interface import PIIMaskerInterface


class AWSComprehendMedicalMasker(PIIMaskerInterface):
    """PII masker using AWS Comprehend Medical."""

    def __init__(self) -> None:
        region = os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("comprehendmedical", region_name=region)

    def mask_pii(self, text: str) -> Tuple[str, Dict]:
        if not text:
            return text, {}

        response = self._client.detect_phi(Text=text)
        entities = sorted(response.get("Entities", []), key=lambda e: e["BeginOffset"], reverse=True)
        masked_text = text
        entity_map: Dict[str, Dict] = {}
        for entity in entities:
            original = text[entity["BeginOffset"] : entity["EndOffset"]]
            replacement = f"[{entity['Type']}]"
            masked_text = (
                masked_text[: entity["BeginOffset"]] + replacement + masked_text[entity["EndOffset"] :]
            )
            entity_map[original] = {
                "type": entity["Type"],
                "replacement": replacement,
                "score": entity.get("Score"),
            }
        return masked_text, entity_map

    def detect_pii(self, text: str) -> List[Dict]:
        if not text:
            return []

        response = self._client.detect_phi(Text=text)
        entities = []
        for entity in response.get("Entities", []):
            entities.append(
                {
                    "text": text[entity["BeginOffset"] : entity["EndOffset"]],
                    "type": entity["Type"],
                    "start": entity["BeginOffset"],
                    "end": entity["EndOffset"],
                    "score": entity.get("Score"),
                }
            )
        return entities
