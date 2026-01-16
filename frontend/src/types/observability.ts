// CloudWatch-compatible structure (mirrors AWS CloudWatch GetMetricData)
export interface CloudWatchMetric {
  namespace: string;           // "AWS/Lambda", "AWS/ECS", "AWS/AppRunner", etc.
  metricName: string;          // "Invocations", "Duration", "CPUUtilization"
  dimensions: { name: string; value: string }[];
  timestamp: string;           // ISO 8601
  value: number;
  unit: string;                // "Count", "Milliseconds", "Percent"
}

// LangSmith-compatible structure (mirrors LangSmith Run schema)
export interface LangSmithTrace {
  runId: string;
  name: string;
  runType: 'chain' | 'llm' | 'tool' | 'retriever';
  startTime: string;
  endTime: string;
  latencyMs: number;
  tokenUsage?: {
    prompt: number;
    completion: number;
    total: number;
  };
  status: 'success' | 'error';
  parentRunId?: string;
}

// Reranker Stats (from /rerank/stats endpoint)
export interface RerankerStats {
  model_name: string;
  device: string;
  cache_hits: number;
  cache_misses: number;
  cache_size: number;
}

// Aggregated metrics for display
export interface MetricSummary {
  label: string;
  value: number | string;
  change?: number;
  changeType?: 'increase' | 'decrease' | 'neutral';
  unit?: string;
  sparklineData?: number[];
}

// Service abstraction interface for future migration
export interface ObservabilityService {
  getCloudWatchMetrics(namespace?: string): Promise<CloudWatchMetric[]>;
  getLangSmithTraces(limit?: number): Promise<LangSmithTrace[]>;
  getRerankerStats(): Promise<RerankerStats>;
  getServiceHealth(): Promise<import('./index').ServiceHealth[]>;
}
