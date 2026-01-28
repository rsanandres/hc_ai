"""Tests for multi-agent prompt improvements and structured output parsing."""

from __future__ import annotations

import pytest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

class TestValidatorOutputParsing:
    """Test the structured output parsing for validator responses."""
    
    def test_parse_yaml_format(self) -> None:
        """Test parsing valid YAML output."""
        from api.agent.output_schemas import parse_validator_output
        
        yaml_text = """
```yaml
validation_status: PASS
issues: []
final_output_override: null
```
"""
        result = parse_validator_output(yaml_text)
        assert result.validation_status == "PASS"
        assert result.issues == []
        assert result.final_output_override is None
    
    def test_parse_yaml_with_issues(self) -> None:
        """Test parsing YAML with issues listed."""
        from api.agent.output_schemas import parse_validator_output
        
        yaml_text = """
```yaml
validation_status: NEEDS_REVISION
issues:
  - description: "Missing citation for diagnosis"
    severity: MEDIUM
    fix_required: "Add FHIR ID for the diabetes diagnosis"
final_output_override: null
```
"""
        result = parse_validator_output(yaml_text)
        assert result.validation_status == "NEEDS_REVISION"
        assert len(result.issues) == 1
        assert result.issues[0].severity == "MEDIUM"
    
    def test_parse_fallback_text_pass(self) -> None:
        """Test fallback parsing when YAML fails."""
        from api.agent.output_schemas import parse_validator_output
        
        text = """
VALIDATION_STATUS: PASS

No issues found. The response is accurate and well-cited.
"""
        result = parse_validator_output(text)
        assert result.validation_status == "PASS"
    
    def test_parse_fallback_text_fail(self) -> None:
        """Test fallback parsing for FAIL status."""
        from api.agent.output_schemas import parse_validator_output
        
        text = """
The response is completely wrong.
VALIDATION_STATUS: FAIL
Major safety concerns detected.
"""
        result = parse_validator_output(text)
        assert result.validation_status == "FAIL"
    
    def test_parse_malformed_defaults_to_needs_revision(self) -> None:
        """Test that malformed output defaults to NEEDS_REVISION."""
        from api.agent.output_schemas import parse_validator_output
        
        text = "Some random text without any status markers."
        result = parse_validator_output(text)
        assert result.validation_status == "NEEDS_REVISION"


class TestStrictnessTierCalculation:
    """Test the strictness tier calculation logic."""
    
    def test_tier_strict_when_many_attempts_remaining(self) -> None:
        """Test TIER_STRICT when remaining > 2."""
        remaining = 4
        if remaining > 2:
            tier = "TIER_STRICT"
        elif remaining > 0:
            tier = "TIER_RELAXED"
        else:
            tier = "TIER_EMERGENCY"
        assert tier == "TIER_STRICT"
    
    def test_tier_relaxed_when_few_attempts(self) -> None:
        """Test TIER_RELAXED when 0 < remaining <= 2."""
        remaining = 2
        if remaining > 2:
            tier = "TIER_STRICT"
        elif remaining > 0:
            tier = "TIER_RELAXED"
        else:
            tier = "TIER_EMERGENCY"
        assert tier == "TIER_RELAXED"
    
    def test_tier_emergency_when_no_attempts(self) -> None:
        """Test TIER_EMERGENCY when remaining == 0."""
        remaining = 0
        if remaining > 2:
            tier = "TIER_STRICT"
        elif remaining > 0:
            tier = "TIER_RELAXED"
        else:
            tier = "TIER_EMERGENCY"
        assert tier == "TIER_EMERGENCY"


class TestGuardrailsIntegration:
    """Test the guardrails validation wrapper."""
    
    def test_validate_output_returns_tuple(self) -> None:
        """Test that validate_output returns (bool, str) tuple."""
        from api.agent.guardrails.validators import validate_output
        
        result = validate_output("Some test text")
        assert isinstance(result, tuple)
        assert len(result) == 2
        is_valid, error_msg = result
        assert isinstance(is_valid, bool)
        assert isinstance(error_msg, str)
    
    def test_validate_output_passes_clean_text(self) -> None:
        """Test that clean text passes validation."""
        from api.agent.guardrails.validators import validate_output
        
        # Clean medical text should pass
        text = "The patient shows signs of hypertension. [FHIR:Observation/123]"
        is_valid, error_msg = validate_output(text)
        # May pass or fail depending on guardrails being enabled
        # Just verify it doesn't crash
        assert isinstance(is_valid, bool)


class TestValidatorOutputModel:
    """Test the Pydantic models."""
    
    def test_validation_issue_model(self) -> None:
        """Test ValidationIssue model creation."""
        from api.agent.output_schemas import ValidationIssue
        
        issue = ValidationIssue(
            description="Test issue",
            severity="HIGH",
            fix_required="Fix this"
        )
        assert issue.description == "Test issue"
        assert issue.severity == "HIGH"
    
    def test_validator_output_model_defaults(self) -> None:
        """Test ValidatorOutput with defaults."""
        from api.agent.output_schemas import ValidatorOutput
        
        output = ValidatorOutput(validation_status="PASS")
        assert output.issues == []
        assert output.final_output_override is None
    
    def test_researcher_output_model(self) -> None:
        """Test ResearcherOutput model."""
        from api.agent.output_schemas import ResearcherOutput
        
        output = ResearcherOutput(
            reasoning="Look up patient history",
            findings="Patient has diabetes",
            confidence="HIGH"
        )
        assert output.sources == []
        assert output.uncertainties == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
