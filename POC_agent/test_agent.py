"""Unit tests for agent components."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from POC_agent.agent.tools import calculate
from POC_agent.pii_masker.local_masker import LocalPIIMasker


class TestPIIMasker(unittest.TestCase):
    def test_mask_pii_basic(self) -> None:
        masker = LocalPIIMasker()
        text = "Contact me at test@example.com on 01/02/2024."
        masked, entity_map = masker.mask_pii(text)
        self.assertIn("[EMAIL]", masked)
        self.assertIn("[DATE]", masked)
        self.assertTrue(entity_map)


class TestTools(unittest.TestCase):
    def test_calculate(self) -> None:
        result = calculate.invoke("2 + 2")
        self.assertEqual(result, "4")


if __name__ == "__main__":
    unittest.main()
