import { AgentQueryRequest, AgentQueryResponse, ServiceHealth } from '@/types';
import { RerankerStats, LangSmithTrace } from '@/types/observability';
import { getEmbeddingsHealth } from './embeddingsApi';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const LANGSMITH_API_URL = process.env.NEXT_PUBLIC_LANGSMITH_API_URL || 'https://api.smith.langchain.com';
const LANGSMITH_API_KEY = process.env.NEXT_PUBLIC_LANGSMITH_API_KEY;

// Retry configuration
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second base delay
const REQUEST_TIMEOUT = 300000; // 5 minutes for agent queries (remote backend)
const HEALTH_CHECK_TIMEOUT = 30000; // 30 seconds for health checks (remote backend)
const DATABASE_TIMEOUT = 120000; // 2 minutes for database queries (remote backend)

// Exponential backoff retry helper
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = MAX_RETRIES,
  baseDelay: number = RETRY_DELAY
): Promise<T> {
  let lastError: Error;
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      if (i < maxRetries - 1) {
        const delay = baseDelay * Math.pow(2, i);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError!;
}

// Fetch with timeout
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = REQUEST_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    console.log(`[fetchWithTimeout] ${options.method || 'GET'} ${url}`, {
      hasBody: !!options.body,
      timeout,
    });

    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    console.log(`[fetchWithTimeout] Response: ${response.status} ${response.statusText}`, {
      url,
      ok: response.ok,
      headers: Object.fromEntries(response.headers.entries()),
    });

    return response;
  } catch (error) {
    clearTimeout(timeoutId);

    // Handle different error types
    const errorMessage = error instanceof Error ? error.message : String(error);
    const errorName = error instanceof Error ? error.name : 'UnknownError';
    const errorStack = error instanceof Error ? error.stack : undefined;

    if (errorName === 'AbortError') {
      const timeoutError = new Error(`Request timeout after ${timeout}ms: ${options.method || 'GET'} ${url}`);
      console.error('[fetchWithTimeout] Timeout error:', {
        url,
        method: options.method || 'GET',
        timeout,
      });
      throw timeoutError;
    }

    // Check for network/CORS errors
    const isNetworkError = errorMessage.includes('Failed to fetch') ||
      errorMessage.includes('NetworkError') ||
      errorMessage.includes('Network request failed') ||
      errorName === 'TypeError' ||
      errorName === 'NetworkError';

    if (isNetworkError) {
      const networkError = new Error(
        `Network error: Unable to connect to ${url}. ` +
        `This may be due to CORS issues, service being down, or network connectivity. ` +
        `Original error: ${errorMessage}`
      );
      console.error('[fetchWithTimeout] Network error:', {
        url,
        method: options.method || 'GET',
        errorMessage,
        errorName,
        errorStack,
        error: error, // Include full error object for debugging
      });
      throw networkError;
    }

    // For any other error, wrap it with context
    const contextError = new Error(
      `Request failed: ${errorMessage} (${options.method || 'GET'} ${url})`
    );
    console.error('[fetchWithTimeout] Unexpected error:', {
      url,
      method: options.method || 'GET',
      errorMessage,
      errorName,
      errorStack,
      error: error, // Include full error object for debugging
    });
    throw contextError;
  }
}

export async function queryAgent(request: AgentQueryRequest): Promise<AgentQueryResponse> {
  return retryWithBackoff(async () => {
    try {
      console.log('[queryAgent] Sending query:', {
        sessionId: request.session_id,
        queryLength: request.query.length,
        userId: request.user_id,
      });

      const response = await fetchWithTimeout(
        `${API_BASE_URL}/agent/query`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        },
        REQUEST_TIMEOUT
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText);
        const error = new Error(
          `Agent query failed: ${response.status} ${response.statusText}. ${errorText}`
        );
        console.error('[queryAgent] HTTP error:', {
          status: response.status,
          statusText: response.statusText,
          errorText,
          sessionId: request.session_id,
        });
        throw error;
      }

      const data = await response.json();
      console.log('[queryAgent] Success:', {
        sessionId: data.session_id,
        responseLength: data.response?.length || 0,
        sourcesCount: data.sources?.length || 0,
      });
      return data;
    } catch (error) {
      console.error('[queryAgent] Error:', {
        sessionId: request.session_id,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      });
      throw error;
    }
  });
}

export async function getAgentHealth(): Promise<ServiceHealth> {
  try {
    const start = Date.now();
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/agent/health`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
    const latency = Date.now() - start;

    if (!response.ok) {
      console.error(`Agent health check failed: ${response.status} ${response.statusText}`);
      return {
        name: 'Agent Service',
        status: 'unhealthy',
        latency,
        lastChecked: new Date(),
      };
    }

    // Parse response to verify it's valid JSON
    const data = await response.json();
    console.log('Agent health check successful:', data);

    return {
      name: 'Agent Service',
      status: 'healthy',
      latency,
      lastChecked: new Date(),
    };
  } catch (error) {
    console.error('Agent health check error:', error);
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
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/retrieval/rerank/health`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
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
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/retrieval/rerank/stats`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function clearSession(sessionId: string): Promise<void> {
  await retryWithBackoff(async () => {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/session/${sessionId}`,
      {
        method: 'POST',
      },
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      throw new Error(`Failed to clear session: ${response.statusText}`);
    }
  });
}

// LangSmith API integration
export async function getLangSmithTraces(limit: number = 10): Promise<LangSmithTrace[]> {
  if (!LANGSMITH_API_KEY) {
    return [];
  }

  try {
    const projectName = 'hc_ai testing';
    const response = await fetchWithTimeout(
      `${LANGSMITH_API_URL}/api/v1/runs?project_name=${encodeURIComponent(projectName)}&limit=${limit}`,
      {
        headers: {
          'Authorization': `Bearer ${LANGSMITH_API_KEY}`,
          'Content-Type': 'application/json',
        },
      },
      HEALTH_CHECK_TIMEOUT
    );

    if (!response.ok) {
      console.warn('Failed to fetch LangSmith traces:', response.statusText);
      return [];
    }

    const data = await response.json();
    const runs = data.runs || [];

    return runs.map(      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (run: any) => ({
        runId: run.id || '',
        name: run.name || 'Unknown',
        runType: (run.run_type || 'chain') as 'chain' | 'llm' | 'tool' | 'retriever',
        startTime: run.start_time || new Date().toISOString(),
        endTime: run.end_time || new Date().toISOString(),
        latencyMs: run.total_tokens ? 0 : (run.latency_ms || 0),
        tokenUsage: run.total_tokens ? {
          prompt: run.prompt_tokens || 0,
          completion: run.completion_tokens || 0,
          total: run.total_tokens || 0,
        } : undefined,
        status: run.status === 'error' ? 'error' : 'success',
        parentRunId: run.parent_run_id,
      }));
  } catch (error) {
    console.warn('Error fetching LangSmith traces:', error);
    return [];
  }
}

// Re-export embeddings health for convenience
export { getEmbeddingsHealth };

// Session Management API (calls reranker service)
import { SessionMetadata, SessionCreateRequest, SessionUpdateRequest, SessionListResponse, SessionCountResponse } from '@/types';

export async function getSessions(userId: string): Promise<SessionListResponse> {
  return retryWithBackoff(async () => {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/session/list?user_id=${encodeURIComponent(userId)}`,
        {},
        HEALTH_CHECK_TIMEOUT
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText);
        const error = new Error(
          `Failed to fetch sessions: ${response.status} ${response.statusText}. ${errorText}`
        );
        console.error('[getSessions] HTTP error:', {
          status: response.status,
          statusText: response.statusText,
          errorText,
          url: `${API_BASE_URL}/session/list?user_id=${encodeURIComponent(userId)}`,
        });
        throw error;
      }

      const data = await response.json();
      console.log('[getSessions] Success:', { userId, sessionCount: data.sessions?.length || 0 });
      return data;
    } catch (error) {
      console.error('[getSessions] Error:', {
        userId,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      });
      throw error;
    }
  });
}

export async function getSessionCount(userId: string): Promise<SessionCountResponse> {
  return retryWithBackoff(async () => {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/session/count?user_id=${encodeURIComponent(userId)}`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      throw new Error(`Failed to get session count: ${response.statusText}`);
    }
    return response.json();
  });
}

export async function createSession(userId: string, metadata?: Partial<SessionCreateRequest>): Promise<SessionMetadata> {
  return retryWithBackoff(async () => {
    try {
      const payload = {
        user_id: userId,
        ...metadata,
      };

      console.log('[createSession] Creating session:', { userId, metadata });

      const response = await fetchWithTimeout(
        `${API_BASE_URL}/session/create`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        },
        HEALTH_CHECK_TIMEOUT
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText);
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { detail: errorText };
        }

        if (errorData.code === 'SESSION_LIMIT_EXCEEDED' || errorData.detail?.code === 'SESSION_LIMIT_EXCEEDED') {
          const limitError = new Error('SESSION_LIMIT_EXCEEDED');
          console.error('[createSession] Session limit exceeded:', { userId });
          throw limitError;
        }

        const error = new Error(
          `Failed to create session: ${response.status} ${response.statusText}. ${errorData.detail || errorText}`
        );
        console.error('[createSession] HTTP error:', {
          status: response.status,
          statusText: response.statusText,
          errorData,
          userId,
        });
        throw error;
      }

      const data = await response.json();
      console.log('[createSession] Success:', { sessionId: data.session_id, userId });
      return data;
    } catch (error) {
      console.error('[createSession] Error:', {
        userId,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      });
      throw error;
    }
  });
}

export async function getSessionMetadata(sessionId: string): Promise<SessionMetadata> {
  return retryWithBackoff(async () => {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/session/${sessionId}/metadata`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      throw new Error(`Failed to get session metadata: ${response.statusText}`);
    }
    return response.json();
  });
}

export async function updateSessionMetadata(sessionId: string, metadata: SessionUpdateRequest): Promise<SessionMetadata> {
  return retryWithBackoff(async () => {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/session/${sessionId}/metadata`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(metadata),
      },
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      throw new Error(`Failed to update session: ${response.statusText}`);
    }
    return response.json();
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  return retryWithBackoff(async () => {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/session/${sessionId}`,
      {
        method: 'DELETE',
      },
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      throw new Error(`Failed to delete session: ${response.statusText}`);
    }
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getSessionMessages(sessionId: string, limit: number = 50): Promise<any[]> {
  return retryWithBackoff(async () => {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/session/${sessionId}?limit=${limit}`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      throw new Error(`Failed to get session messages: ${response.statusText}`);
    }
    const data = await response.json();
    return data.recent_turns || [];
  });
}

// Database API functions
export interface PatientSummary {
  id: string;
  name: string;
  chunk_count: number;
  resource_types: string[];
}

export async function listPatients(): Promise<PatientSummary[]> {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/db/patients`,
      {},
      DATABASE_TIMEOUT
    );
    if (!response.ok) {
      console.error('Failed to list patients:', response.statusText);
      return [];
    }
    const data = await response.json();
    return data.patients || [];
  } catch (error) {
    console.error('Error listing patients:', error);
    return [];
  }
}

export async function getDatabaseStats(): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/db/stats`,
      {},
      DATABASE_TIMEOUT
    );
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    console.error('Error getting database stats:', error);
    return null;
  }
}

// CloudWatch metrics response
export interface CloudWatchMetricsResponse {
  metrics: {
    id: string;
    namespace: string;
    metricName: string;
    stat: string;
    timestamps: string[];
    values: number[];
    latest: number | null;
  }[];
  cached: boolean;
  fetched_at: string;
  error?: string;
}

export async function getCloudWatchMetrics(): Promise<CloudWatchMetricsResponse | null> {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/db/cloudwatch`,
      {},
      HEALTH_CHECK_TIMEOUT
    );
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    console.error('Error getting CloudWatch metrics:', error);
    return null;
  }
}

export async function getErrorCounts(): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/db/errors/counts`,
      {},
      DATABASE_TIMEOUT
    );
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    console.error('Error getting error counts:', error);
    return null;
  }
}
