"""MCP -> LangChain tool adapter utilities."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.tools import tool

from POC_agent.mcp.manager import MCPServerManager
from POC_agent.mcp.servers import MCP_AGENT_TOOL_ALLOWLIST


def _build_tool_wrapper(client, tool_name: str, description: str | None):
    @tool(name=tool_name, description=description or "")
    async def _tool(**kwargs: Any) -> Any:
        return await client.call_tool(tool_name, kwargs)

    return _tool


async def build_mcp_tools_for_agent(agent_role: str, manager: MCPServerManager) -> List[Any]:
    tools: List[Any] = []
    allowlist = MCP_AGENT_TOOL_ALLOWLIST.get(agent_role, {})

    for server_name, allowed_tools in allowlist.items():
        client = await manager.get_client(server_name)
        available = await client.list_tools()
        for tool_schema in available:
            tool_name = tool_schema.get("name")
            if not tool_name or tool_name not in allowed_tools:
                continue
            description = tool_schema.get("description", "")
            tools.append(_build_tool_wrapper(client, tool_name, description))
    return tools
