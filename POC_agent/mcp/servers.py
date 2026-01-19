"""MCP server configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None


MCP_SERVERS: Dict[str, MCPServerConfig] = {
    "agentcare": MCPServerConfig(
        name="agentcare",
        command="npx",
        args=["@kartha-ai/agentcare-mcp"],
    ),
    "healthcare-mcp-public": MCPServerConfig(
        name="healthcare-mcp-public",
        command="npx",
        args=["healthcare-mcp-public"],
    ),
    "certus": MCPServerConfig(
        name="certus",
        command="npx",
        args=["@zesty-genius128/certus-mcp"],
    ),
    "medical-mcp": MCPServerConfig(
        name="medical-mcp",
        command="npx",
        args=["@jamesanz/medical-mcp"],
    ),
    "langsmith": MCPServerConfig(
        name="langsmith",
        command="npx",
        args=["@langchain/langsmith-mcp"],
    ),
}


MCP_AGENT_TOOL_ALLOWLIST: Dict[str, Dict[str, List[str]]] = {
    "researcher": {
        "agentcare": [
            "get_patient_data",
            "search_conditions",
            "get_drug_interactions",
            "search_pubmed",
            "search_clinical_trials",
        ],
        "healthcare-mcp-public": [
            "search_icd10",
            "search_clinical_trials",
            "search_pubmed",
            "search_fda_drugs",
        ],
        "certus": [
            "get_drug_shortages",
            "get_drug_recalls",
        ],
    },
    "validator": {
        "medical-mcp": [
            "get_clinical_guidelines",
            "lookup_rxnorm",
            "get_who_stats",
        ],
        "certus": [
            "get_faers_events",
            "get_drug_recalls",
        ],
        "healthcare-mcp-public": [
            "validate_icd10_code",
        ],
    },
}
