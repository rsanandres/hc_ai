// Agent API Types (matches backend api/agent/models.py)
export interface AgentDocument {
  doc_id: string;
  content_preview: string;
  metadata: Record<string, unknown>;
}

export interface AgentQueryRequest {
  query: string;
  session_id: string;
  user_id?: string;
  patient_id?: string;
  k_retrieve?: number;
  k_return?: number;
}

export interface AgentQueryResponse {
  query: string;
  response: string;
  researcher_output?: string;
  validator_output?: string;
  validation_result?: string;
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
  researcherOutput?: string;
  validatorOutput?: string;
  validationResult?: string;
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

// Session Management Types
export interface SessionMetadata {
  session_id: string;
  user_id: string;
  name?: string;
  description?: string;
  tags: string[];
  created_at: string;
  last_activity: string;
  message_count: number;
  first_message_preview?: string;
}

export interface SessionCreateRequest {
  user_id: string;
  name?: string;
  description?: string;
  tags?: string[];
}

export interface SessionUpdateRequest {
  name?: string;
  description?: string;
  tags?: string[];
}

export interface SessionListResponse {
  sessions: SessionMetadata[];
  count: number;
}

export interface SessionCountResponse {
  user_id: string;
  count: number;
  max_allowed: number;
}

export interface StreamEvent {
  type: 'tool_call' | 'researcher_output' | 'validator_output' | 'final_response';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}
