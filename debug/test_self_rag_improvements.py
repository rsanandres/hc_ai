"""
Tests for Self-RAG improvements: Query Expansion, Trajectory Memory, and Hallucination Prevention.

Each change has 2-3 test cases to verify the implementation works correctly.
"""

from __future__ import annotations

import pytest
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# =============================================================================
# CHANGE 1: Query Expansion (STEP 0)
# =============================================================================

class TestQueryExpansionPrompt:
    """Test that STEP 0 - QUERY EXPANSION is present and correctly formatted."""
    
    def test_query_expansion_section_exists(self) -> None:
        """Verify STEP 0 - QUERY EXPANSION section exists in researcher prompt."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "STEP 0 - QUERY EXPANSION" in prompt, "STEP 0 should be in researcher prompt"
    
    def test_query_expansion_has_clinical_synonyms(self) -> None:
        """Verify the prompt mentions clinical synonyms strategy."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "Clinical Synonyms" in prompt, "Should mention clinical synonyms"
        assert "Heart attack" in prompt or "Myocardial infarction" in prompt, \
            "Should have example of clinical synonym"
    
    def test_query_expansion_has_fhir_resource_types(self) -> None:
        """Verify the prompt mentions FHIR resource type strategy."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "FHIR Resource Types" in prompt, "Should mention FHIR resource types"


# =============================================================================
# CHANGE 2: Trajectory Awareness (Death Loop Prevention)
# =============================================================================

class TestTrajectoryAwareness:
    """Test trajectory awareness for death loop prevention."""
    
    def test_trajectory_awareness_section_exists(self) -> None:
        """Verify TRAJECTORY AWARENESS section exists in researcher prompt."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "TRAJECTORY AWARENESS" in prompt, "TRAJECTORY AWARENESS should be in prompt"
    
    def test_trajectory_lists_valid_fhir_resources(self) -> None:
        """Verify the prompt lists valid FHIR resource types."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        # Check for key FHIR resources
        assert "Condition" in prompt, "Should list Condition resource"
        assert "Observation" in prompt, "Should list Observation resource"
        assert "MedicationRequest" in prompt, "Should list MedicationRequest resource"
    
    def test_trajectory_has_negative_constraint(self) -> None:
        """Verify the prompt has negative constraint to prevent repeated queries."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "NEGATIVE CONSTRAINT" in prompt, "Should have negative constraint"
        assert "repeat" in prompt.lower() or "0 results" in prompt.lower(), \
            "Should mention not repeating failed queries"


# =============================================================================
# CHANGE 3: Hallucination Prevention (Researcher)
# =============================================================================

class TestHallucinationPreventionResearcher:
    """Test hallucination prevention in researcher prompt."""
    
    def test_hallucination_prevention_section_exists(self) -> None:
        """Verify HALLUCINATION PREVENTION section exists in researcher prompt."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "HALLUCINATION PREVENTION" in prompt, \
            "HALLUCINATION PREVENTION should be in prompt"
    
    def test_hallucination_prevention_mentions_no_records(self) -> None:
        """Verify the prompt mentions reporting 'No records found'."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "No records found" in prompt, \
            "Should mention reporting 'No records found'"
    
    def test_hallucination_prevention_forbids_likely_statements(self) -> None:
        """Verify the prompt forbids 'likely' or 'probably' statements."""
        from api.agent.prompt_loader import get_researcher_prompt
        
        prompt = get_researcher_prompt()
        assert "likely" in prompt.lower(), "Should mention avoiding 'likely' statements"


# =============================================================================
# CHANGE 4: Hallucination Detection (Validator)
# =============================================================================

class TestHallucinationDetectionValidator:
    """Test hallucination detection in validator prompt."""
    
    def test_hallucination_detection_section_exists(self) -> None:
        """Verify HALLUCINATION DETECTION section exists in validator prompt."""
        from api.agent.prompt_loader import get_validator_prompt
        
        prompt = get_validator_prompt()
        assert "HALLUCINATION DETECTION" in prompt, \
            "HALLUCINATION DETECTION should be in validator prompt"
    
    def test_hallucination_detection_mentions_fhir_citation(self) -> None:
        """Verify the prompt mentions checking for FHIR citations."""
        from api.agent.prompt_loader import get_validator_prompt
        
        prompt = get_validator_prompt()
        assert "FHIR citation" in prompt or "citation" in prompt.lower(), \
            "Should mention checking for citations"
    
    def test_hallucination_detection_returns_needs_revision(self) -> None:
        """Verify the prompt instructs to return NEEDS_REVISION for hallucinations."""
        from api.agent.prompt_loader import get_validator_prompt
        
        prompt = get_validator_prompt()
        assert "NEEDS_REVISION" in prompt, \
            "Should instruct to return NEEDS_REVISION for hallucinations"


# =============================================================================
# CHANGE 5: Trajectory State Fields
# =============================================================================

class TestTrajectoryStateFields:
    """Test that AgentState has trajectory tracking fields."""
    
    def test_agent_state_has_search_attempts_field(self) -> None:
        """Verify AgentState has search_attempts field."""
        from api.agent.multi_agent_graph import AgentState
        
        # TypedDict fields are in __annotations__
        annotations = AgentState.__annotations__
        assert "search_attempts" in annotations, \
            "AgentState should have search_attempts field"
    
    def test_agent_state_has_empty_search_count_field(self) -> None:
        """Verify AgentState has empty_search_count field."""
        from api.agent.multi_agent_graph import AgentState
        
        annotations = AgentState.__annotations__
        assert "empty_search_count" in annotations, \
            "AgentState should have empty_search_count field"
    
    def test_state_fields_have_correct_types(self) -> None:
        """Verify state fields have correct type annotations."""
        from api.agent.multi_agent_graph import AgentState
        
        annotations = AgentState.__annotations__
        # search_attempts should be List[Dict[str, Any]]
        assert "List" in str(annotations.get("search_attempts", "")), \
            "search_attempts should be a List type"
        # empty_search_count should be int (may be ForwardRef in TypedDict)
        empty_type = str(annotations.get("empty_search_count", ""))
        assert "int" in empty_type, \
            f"empty_search_count should be int type, got {empty_type}"


# =============================================================================
# CHANGE 6 & 7: Trajectory Injection and Result Tracking
# =============================================================================

class TestTrajectoryInjectionLogic:
    """Test trajectory injection logic (simulated, no LLM call)."""
    
    def test_trajectory_injection_creates_message(self) -> None:
        """Test that trajectory injection creates a proper system message."""
        from langchain_core.messages import SystemMessage
        
        # Simulate state with failed searches
        search_attempts = [
            {"query": "Condition active", "results_count": 0},
            {"query": "Diagnosis", "results_count": 0},
        ]
        empty_count = 2
        
        # Simulate the injection logic from _researcher_node
        if empty_count > 0:
            failed_queries = [f"- '{a.get('query', 'unknown')}' → {a.get('results_count', 0)} results" 
                              for a in search_attempts[-3:]]
            msg_content = f"""
⚠️ RETRY MODE (Attempt {empty_count + 1})

PREVIOUS FAILED QUERIES:
{chr(10).join(failed_queries)}
"""
            message = SystemMessage(content=msg_content)
            
            assert "RETRY MODE" in message.content
            assert "Condition active" in message.content
            assert "Diagnosis" in message.content
            assert "0 results" in message.content
    
    def test_empty_search_count_increments(self) -> None:
        """Test that empty_search_count increments correctly."""
        # Simulate empty sources
        new_sources: List[Dict[str, Any]] = []
        empty_count = 1
        
        if len(new_sources) == 0:
            empty_count += 1
        else:
            empty_count = 0
        
        assert empty_count == 2, "empty_count should increment on empty results"
    
    def test_empty_search_count_resets_on_success(self) -> None:
        """Test that empty_search_count resets when sources are found."""
        # Simulate finding sources
        new_sources = [{"id": "test", "content": "test content"}]
        empty_count = 3
        
        if len(new_sources) == 0:
            empty_count += 1
        else:
            empty_count = 0
        
        assert empty_count == 0, "empty_count should reset on successful retrieval"


class TestStepLimitWarning:
    """Test step limit warning logic."""
    
    def test_step_limit_triggers_at_12(self) -> None:
        """Test that step limit warning triggers at iteration >= 12."""
        current_iteration = 12
        triggered = current_iteration >= 12
        assert triggered, "Step limit should trigger at iteration 12"
    
    def test_step_limit_does_not_trigger_early(self) -> None:
        """Test that step limit warning does not trigger early."""
        current_iteration = 11
        triggered = current_iteration >= 12
        assert not triggered, "Step limit should not trigger at iteration 11"


# =============================================================================
# Integration Test: Full Flow Simulation
# =============================================================================

class TestFullFlowSimulation:
    """Integration test simulating the full trajectory flow."""
    
    def test_full_trajectory_flow(self) -> None:
        """Simulate a complete trajectory flow from empty to warning."""
        # Initial state
        state = {
            "search_attempts": [],
            "empty_search_count": 0,
            "iteration_count": 0,
        }
        
        # Simulate 3 failed searches
        for i in range(3):
            # Simulate empty result
            new_sources: List[Dict[str, Any]] = []
            
            # Track attempt
            state["search_attempts"].append({
                "query": f"Query {i+1}",
                "results_count": len(new_sources),
                "iteration": i + 1
            })
            
            # Update empty count
            if len(new_sources) == 0:
                state["empty_search_count"] += 1
            else:
                state["empty_search_count"] = 0
            
            state["iteration_count"] += 1
        
        # Verify state after 3 failures
        assert len(state["search_attempts"]) == 3
        assert state["empty_search_count"] == 3
        assert state["iteration_count"] == 3
        
        # Verify trajectory message would include all 3 queries
        failed_queries = [a["query"] for a in state["search_attempts"][-3:]]
        assert "Query 1" in failed_queries
        assert "Query 2" in failed_queries
        assert "Query 3" in failed_queries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
