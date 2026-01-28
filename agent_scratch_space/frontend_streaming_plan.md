# Future Task: Frontend Streaming Implementation

## Objective
Enable real-time streaming responses in the chat interface using Server-Sent Events (SSE).

## Backend Status
- Endpoint `/agent/query/stream` already exists in `api/agent/router.py`.
- Returns SSE stream with JSON data: `data: {"type": "token", "content": "..."}`.

## Frontend Implementation Requirements

### 1. Update API Service (`src/services/agentApi.ts`)
Add `queryAgentStream` function that handles SSE connection:

```typescript
export async function queryAgentStream(
  request: AgentQueryRequest, 
  onMessage: (chunk: string) => void,
  onTool: (tool: ToolCall) => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/agent/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  
  // readership loop...
}
```

### 2. Create `useChatStream` Hook
New React hook to replace or augment `useChat`:
- Manage streaming state (isStreaming, currentResponse)
- Accumulate partial tokens
- Handle "tool_start" and "tool_end" events to show tool UI updates in real-time

### 3. Update Chat UI Components
- **MessageBubble:** Needs to handle streaming text updates smoothly (prevent jitter).
- **ToolIndicator:** Needs to show "Thinking..." or specifics based on stream events before the final response arrives.

## Estimated Effort
- **Complexity:** Medium/High
- **Files:** ~4-5 files
