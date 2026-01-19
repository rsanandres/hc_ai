"""MCP server lifecycle manager."""

from __future__ import annotations

from typing import Dict

from POC_agent.mcp.client import MCPClient, MCPClientConfig
from POC_agent.mcp.servers import MCP_SERVERS


class MCPServerManager:
    """Manage MCP server clients."""

    def __init__(self) -> None:
        self._clients: Dict[str, MCPClient] = {}

    async def get_client(self, name: str) -> MCPClient:
        if name in self._clients:
            return self._clients[name]
        if name not in MCP_SERVERS:
            raise ValueError(f"Unknown MCP server: {name}")
        config = MCP_SERVERS[name]
        client = MCPClient(
            name=name,
            config=MCPClientConfig(command=config.command, args=config.args, env=config.env),
        )
        await client.connect()
        self._clients[name] = client
        return client

    async def shutdown_all(self) -> None:
        for client in list(self._clients.values()):
            await client.close()
        self._clients.clear()
