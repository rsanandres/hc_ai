"""MCP client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except Exception as exc:  # pragma: no cover - handled at runtime
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass
class MCPClientConfig:
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None


class MCPClient:
    """Async MCP client using stdio transport."""

    def __init__(self, name: str, config: MCPClientConfig):
        self.name = name
        self.config = config
        self._stdio_cm = None
        self._session_cm = None
        self._session = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        if _IMPORT_ERROR is not None:
            raise RuntimeError(f"MCP client dependency missing: {_IMPORT_ERROR}") from _IMPORT_ERROR

        params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env,
        )
        self._stdio_cm = stdio_client(params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()

    async def list_tools(self) -> List[Dict[str, Any]]:
        await self.connect()
        tools = await self._session.list_tools()
        return tools.tools if hasattr(tools, "tools") else tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        await self.connect()
        result = await self._session.call_tool(name, arguments)
        return result.content if hasattr(result, "content") else result

    async def ping(self) -> bool:
        await self.connect()
        return True

    async def close(self) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(None, None, None)
            self._session_cm = None
            self._session = None
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(None, None, None)
            self._stdio_cm = None
