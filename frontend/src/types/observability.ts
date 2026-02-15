// CloudWatch-compatible structure (mirrors AWS CloudWatch GetMetricData)
export interface CloudWatchMetric {
  namespace: string;           // "AWS/Lambda", "AWS/ECS", "AWS/AppRunner", etc.
  metricName: string;          // "Invocations", "Duration", "CPUUtilization"
  dimensions: { name: string; value: string }[];
  timestamp: string;           // ISO 8601
  value: number;
  unit: string;                // "Count", "Milliseconds", "Percent"
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
  color?: string;
}

// Cost breakdown for pie chart
export interface CostBreakdown {
  service: string;
  cost: number;
  percentage: number;
}

// CloudWatch time-series data for sparklines
export interface CloudWatchTimeSeries {
  id: string;            // e.g. "ecs_cpu", "alb_p50"
  namespace: string;
  metricName: string;
  stat: string;
  timestamps: string[];
  values: number[];
  latest: number | null;
}

// Service abstraction interface for future migration
export interface ObservabilityService {
  getCloudWatchMetrics(namespace?: string): Promise<CloudWatchMetric[]>;
  getRerankerStats(): Promise<RerankerStats>;
  getServiceHealth(): Promise<import('./index').ServiceHealth[]>;
}
