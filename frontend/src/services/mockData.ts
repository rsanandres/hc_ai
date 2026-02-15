import { ServiceHealth } from '@/types';
import { CloudWatchMetric, MetricSummary, RerankerStats, CostBreakdown } from '@/types/observability';

// Helper to generate random values within a range
const randomInRange = (min: number, max: number) => Math.random() * (max - min) + min;
const randomInt = (min: number, max: number) => Math.floor(randomInRange(min, max));

// Generate sparkline data (last 20 data points)
const generateSparkline = (base: number, variance: number, points = 20): number[] => {
  return Array.from({ length: points }, () => 
    Math.max(0, base + randomInRange(-variance, variance))
  );
};

// Mock CloudWatch Metrics
export function getMockCloudWatchMetrics(): CloudWatchMetric[] {
  const now = new Date().toISOString();
  
  return [
    // App Runner metrics
    {
      namespace: 'AWS/AppRunner',
      metricName: 'CPUUtilization',
      dimensions: [{ name: 'ServiceName', value: 'atlas-agent' }],
      timestamp: now,
      value: randomInRange(15, 45),
      unit: 'Percent',
    },
    {
      namespace: 'AWS/AppRunner',
      metricName: 'MemoryUtilization',
      dimensions: [{ name: 'ServiceName', value: 'atlas-agent' }],
      timestamp: now,
      value: randomInRange(30, 60),
      unit: 'Percent',
    },
    {
      namespace: 'AWS/AppRunner',
      metricName: 'RequestCount',
      dimensions: [{ name: 'ServiceName', value: 'atlas-agent' }],
      timestamp: now,
      value: randomInt(100, 500),
      unit: 'Count',
    },
    {
      namespace: 'AWS/AppRunner',
      metricName: 'RequestLatency',
      dimensions: [{ name: 'ServiceName', value: 'atlas-agent' }],
      timestamp: now,
      value: randomInRange(200, 800),
      unit: 'Milliseconds',
    },
    // RDS metrics
    {
      namespace: 'AWS/RDS',
      metricName: 'DatabaseConnections',
      dimensions: [{ name: 'DBInstanceIdentifier', value: 'atlas-postgres' }],
      timestamp: now,
      value: randomInt(5, 25),
      unit: 'Count',
    },
    {
      namespace: 'AWS/RDS',
      metricName: 'CPUUtilization',
      dimensions: [{ name: 'DBInstanceIdentifier', value: 'atlas-postgres' }],
      timestamp: now,
      value: randomInRange(10, 35),
      unit: 'Percent',
    },
    // Bedrock metrics
    {
      namespace: 'AWS/Bedrock',
      metricName: 'InvocationLatency',
      dimensions: [{ name: 'ModelId', value: 'claude-3-5-haiku' }],
      timestamp: now,
      value: randomInRange(800, 2500),
      unit: 'Milliseconds',
    },
    {
      namespace: 'AWS/Bedrock',
      metricName: 'InputTokenCount',
      dimensions: [{ name: 'ModelId', value: 'claude-3-5-haiku' }],
      timestamp: now,
      value: randomInt(500, 2000),
      unit: 'Count',
    },
    {
      namespace: 'AWS/Bedrock',
      metricName: 'OutputTokenCount',
      dimensions: [{ name: 'ModelId', value: 'claude-3-5-haiku' }],
      timestamp: now,
      value: randomInt(100, 800),
      unit: 'Count',
    },
  ];
}

// Mock Reranker Stats
export function getMockRerankerStats(): RerankerStats {
  return {
    model_name: 'sentence-transformers/all-MiniLM-L6-v2',
    device: 'cpu',
    cache_hits: randomInt(500, 2000),
    cache_misses: randomInt(50, 200),
    cache_size: randomInt(1000, 5000),
  };
}

// Mock Service Health
export function getMockServiceHealth(): ServiceHealth[] {
  return [
    {
      name: 'Agent Service',
      status: Math.random() > 0.1 ? 'healthy' : 'degraded',
      latency: randomInt(10, 50),
      lastChecked: new Date(),
    },
    {
      name: 'Reranker Service',
      status: Math.random() > 0.1 ? 'healthy' : 'degraded',
      latency: randomInt(5, 30),
      lastChecked: new Date(),
    },
    {
      name: 'Vector DB (pgvector)',
      status: Math.random() > 0.05 ? 'healthy' : 'unhealthy',
      latency: randomInt(2, 15),
      lastChecked: new Date(),
    },
    {
      name: 'DynamoDB',
      status: 'healthy', // Free tier, always up
      latency: randomInt(5, 20),
      lastChecked: new Date(),
    },
    {
      name: 'Bedrock (Claude)',
      status: Math.random() > 0.02 ? 'healthy' : 'degraded',
      latency: randomInt(100, 300),
      lastChecked: new Date(),
    },
  ];
}

// Aggregated metrics for dashboard cards
export function getMockMetricSummaries(): MetricSummary[] {
  return [
    {
      label: 'Total Requests',
      value: randomInt(1200, 1800),
      change: randomInRange(-5, 15),
      changeType: 'increase',
      unit: 'today',
      sparklineData: generateSparkline(100, 30),
    },
    {
      label: 'Avg Latency',
      value: `${randomInt(400, 700)}ms`,
      change: randomInRange(-10, 5),
      changeType: 'decrease',
      sparklineData: generateSparkline(500, 100),
    },
    {
      label: 'Cache Hit Rate',
      value: `${randomInRange(85, 95).toFixed(1)}%`,
      change: randomInRange(0, 3),
      changeType: 'increase',
      sparklineData: generateSparkline(90, 5),
    },
    {
      label: 'Token Usage',
      value: `${(randomInRange(50, 150)).toFixed(1)}K`,
      change: randomInRange(5, 20),
      changeType: 'increase',
      unit: 'tokens/hr',
      sparklineData: generateSparkline(100, 25),
    },
    {
      label: 'Est. Cost',
      value: `$${randomInRange(2, 8).toFixed(2)}`,
      change: randomInRange(-2, 5),
      changeType: 'neutral',
      unit: 'today',
      sparklineData: generateSparkline(5, 2),
    },
    {
      label: 'Error Rate',
      value: `${randomInRange(0.1, 1.5).toFixed(2)}%`,
      change: randomInRange(-0.5, 0.3),
      changeType: 'decrease',
      sparklineData: generateSparkline(0.5, 0.3),
    },
  ];
}

// Cost breakdown (mocked)
export function getMockCostBreakdown(): CostBreakdown[] {
  const bedrock = randomInRange(25, 35);
  const appRunner = randomInRange(20, 30);
  const rds = randomInRange(18, 25);
  const other = randomInRange(2, 5);
  const total = bedrock + appRunner + rds + other;
  
  return [
    { service: 'Bedrock (LLM)', cost: bedrock, percentage: (bedrock / total) * 100 },
    { service: 'App Runner', cost: appRunner, percentage: (appRunner / total) * 100 },
    { service: 'RDS PostgreSQL', cost: rds, percentage: (rds / total) * 100 },
    { service: 'Other (S3, DynamoDB)', cost: other, percentage: (other / total) * 100 },
  ];
}
