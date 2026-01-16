// Agent API Types (matches backend POC_agent/agent/models.py)
export interface AgentDocument {
  doc_id: string;
  content_preview: string;
  metadata: Record<string, unknown>;
}

export interface AgentQueryRequest {
  query: string;
  session_id: string;
  patient_id?: string;
  k_retrieve?: number;
  k_return?: number;
}

export interface AgentQueryResponse {
  query: string;
  response: string;
  sources: AgentDocument[];
  tool_calls: string[];
  session_id: string;
}

// Chat Types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: AgentDocument[];
  toolCalls?: string[];
  isLoading?: boolean;
}

// Workflow Types
export type PipelineStepStatus = 'pending' | 'active' | 'completed' | 'skipped';

export interface PipelineStep {
  id: string;
  name: string;
  description: string;
  status: PipelineStepStatus;
  duration?: number;
  details?: Record<string, unknown>;
}

// Service Health
export interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency?: number;
  lastChecked: Date;
}
