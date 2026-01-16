import { AgentQueryRequest, AgentQueryResponse, ServiceHealth } from '@/types';
import { RerankerStats } from '@/types/observability';

const AGENT_BASE_URL = process.env.NEXT_PUBLIC_AGENT_URL || 'http://localhost:8000';
const RERANKER_BASE_URL = process.env.NEXT_PUBLIC_RERANKER_URL || 'http://localhost:8001';

export async function queryAgent(request: AgentQueryRequest): Promise<AgentQueryResponse> {
  const response = await fetch(`${AGENT_BASE_URL}/agent/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Agent query failed: ${error}`);
  }

  return response.json();
}

export async function getAgentHealth(): Promise<ServiceHealth> {
  try {
    const start = Date.now();
    const response = await fetch(`${AGENT_BASE_URL}/agent/health`);
    const latency = Date.now() - start;

    if (!response.ok) {
      return {
        name: 'Agent Service',
        status: 'unhealthy',
        latency,
        lastChecked: new Date(),
      };
    }

    return {
      name: 'Agent Service',
      status: 'healthy',
      latency,
      lastChecked: new Date(),
    };
  } catch {
    return {
      name: 'Agent Service',
      status: 'unhealthy',
      lastChecked: new Date(),
    };
  }
}

export async function getRerankerHealth(): Promise<ServiceHealth> {
  try {
    const start = Date.now();
    const response = await fetch(`${RERANKER_BASE_URL}/rerank/health`);
    const latency = Date.now() - start;

    if (!response.ok) {
      return {
        name: 'Reranker Service',
        status: 'unhealthy',
        latency,
        lastChecked: new Date(),
      };
    }

    return {
      name: 'Reranker Service',
      status: 'healthy',
      latency,
      lastChecked: new Date(),
    };
  } catch {
    return {
      name: 'Reranker Service',
      status: 'unhealthy',
      lastChecked: new Date(),
    };
  }
}

export async function getRerankerStats(): Promise<RerankerStats | null> {
  try {
    const response = await fetch(`${RERANKER_BASE_URL}/rerank/stats`);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${AGENT_BASE_URL}/agent/session/${sessionId}/clear`, {
    method: 'POST',
  });
}
