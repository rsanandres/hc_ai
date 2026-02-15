'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getAgentHealth,
  getRerankerHealth,
  getRerankerStats,
  getEmbeddingsHealth,
  getDatabaseStats,
  getErrorCounts,
  getCloudWatchMetrics,
} from '@/services/agentApi';
import { CloudWatchMetric, CloudWatchTimeSeries, MetricSummary, CostBreakdown } from '@/types/observability';
import type { RerankerStats } from '@/types/observability';
import { ServiceHealth } from '@/types';

const REFRESH_INTERVAL = 5000; // 5 seconds for real-time updates

// Database stats type
export interface DatabaseStats {
  active_connections: number;
  max_connections: number;
  pool_size: number;
  pool_overflow: number;
  pool_checked_out: number;
  pool_checked_in: number;
  queue_size: number;
  queue_stats: {
    queued: number;
    processed: number;
    failed: number;
    retries: number;
  };
}

// Initial data (empty, will be populated by first fetch)
function getInitialData() {
  return {
    cloudWatchMetrics: [] as CloudWatchMetric[],
    rerankerStats: null as RerankerStats | null,
    databaseStats: null as DatabaseStats | null,
    serviceHealth: [] as ServiceHealth[],
    metricSummaries: [] as MetricSummary[],
    costBreakdown: [] as CostBreakdown[],
  };
}

export function useObservability() {
  // Initialize with data to avoid calling setState in effect
  const [data, setData] = useState(getInitialData);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [isMaintenanceMode, setIsMaintenanceMode] = useState(false);

  const refreshData = useCallback(async () => {
    setIsLoading(true);
    
    try {
      // Fetch all service health checks in parallel (graceful degradation)
      const [agentHealth, rerankerHealth, embeddingsHealth, rerankerStats, dbStats, errorCounts, cwMetrics] = await Promise.allSettled([
        getAgentHealth(),
        getRerankerHealth(),
        getEmbeddingsHealth(),
        getRerankerStats(),
        getDatabaseStats(),
        getErrorCounts(),
        getCloudWatchMetrics(),
      ]);

      // Build service health array (handle failures gracefully)
      const serviceHealth: ServiceHealth[] = [];
      if (agentHealth.status === 'fulfilled') {
        serviceHealth.push(agentHealth.value);
      } else {
        console.error('Agent health check failed:', agentHealth.reason);
        // Still add unhealthy status so it shows in UI
        serviceHealth.push({
          name: 'Agent Service',
          status: 'unhealthy',
          lastChecked: new Date(),
        });
      }
      if (rerankerHealth.status === 'fulfilled') {
        serviceHealth.push(rerankerHealth.value);
      } else {
        console.error('Reranker health check failed:', rerankerHealth.reason);
        serviceHealth.push({
          name: 'Reranker Service',
          status: 'unhealthy',
          lastChecked: new Date(),
        });
      }
      if (embeddingsHealth.status === 'fulfilled') {
        serviceHealth.push(embeddingsHealth.value);
      } else {
        console.error('Embeddings health check failed:', embeddingsHealth.reason);
        serviceHealth.push({
          name: 'Embeddings Service',
          status: 'unhealthy',
          lastChecked: new Date(),
        });
      }

      // Get reranker stats (null if failed)
      const stats = rerankerStats.status === 'fulfilled' ? rerankerStats.value : null;

      // Get database stats (null if failed)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const databaseStats: any = dbStats.status === 'fulfilled' ? dbStats.value : null;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const errors: any = errorCounts.status === 'fulfilled' ? errorCounts.value : null;

      // Add database health to service health
      // If we got stats without error, the database is healthy (active_connections only counts running queries, not idle connections)
      if (databaseStats && !databaseStats.error) {
        serviceHealth.push({
          name: 'PostgreSQL',
          status: 'healthy',
          latency: undefined,
          lastChecked: new Date(),
        });
      } else if (databaseStats?.error) {
        serviceHealth.push({
          name: 'PostgreSQL',
          status: 'unhealthy',
          lastChecked: new Date(),
        });
      }

      // CloudWatch time-series from backend
      const cwData = cwMetrics.status === 'fulfilled' ? cwMetrics.value : null;
      const cwTimeSeries: CloudWatchTimeSeries[] =
        cwData?.metrics?.map((m: CloudWatchTimeSeries) => ({
          id: m.id,
          namespace: m.namespace,
          metricName: m.metricName,
          stat: m.stat,
          timestamps: m.timestamps,
          values: m.values,
          latest: m.latest,
        })) ?? [];

      const findCW = (id: string) => cwTimeSeries.find(m => m.id === id);

      // Helper: compute trend from a time-series
      const computeTrend = (values: number[]): { change: number; changeType: 'increase' | 'decrease' | 'neutral' } => {
        if (values.length < 2) return { change: 0, changeType: 'neutral' };
        const recent = values[values.length - 1];
        // Compare latest value to the average of the first quarter for stability
        const firstQuarter = values.slice(0, Math.max(1, Math.floor(values.length / 4)));
        const baseline = firstQuarter.reduce((a, b) => a + b, 0) / firstQuarter.length;
        if (baseline === 0) return { change: 0, changeType: 'neutral' };
        const pctChange = ((recent - baseline) / baseline) * 100;
        return {
          change: Math.abs(pctChange),
          changeType: pctChange > 1 ? 'increase' : pctChange < -1 ? 'decrease' : 'neutral',
        };
      };

      // Format a CloudWatch latest value for display
      const fmtValue = (v: number | null | undefined, unit: string): string => {
        if (v == null) return '--';
        if (unit === '%') return `${v.toFixed(1)}%`;
        if (unit === 's') return v < 1 ? `${(v * 1000).toFixed(0)}ms` : `${v.toFixed(2)}s`;
        if (unit === 'count') return v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${Math.round(v)}`;
        return `${v}`;
      };

      // Build CloudWatch-backed metric cards
      const metricSummaries: MetricSummary[] = [];
      const ecsCpu = findCW('ecs_cpu');
      const ecsMem = findCW('ecs_memory');
      const albReq = findCW('alb_requests');
      const rdsCpu = findCW('rds_cpu');
      const rdsConn = findCW('rds_connections');
      const albP99 = findCW('alb_p99');

      const hasCW = cwTimeSeries.length > 0;

      if (hasCW) {
        const cards: { ts: CloudWatchTimeSeries | undefined; label: string; unit: string; color: string }[] = [
          { ts: ecsCpu, label: 'ECS CPU', unit: '%', color: '#14b8a6' },
          { ts: ecsMem, label: 'ECS Memory', unit: '%', color: '#8b5cf6' },
          { ts: albReq, label: 'ALB Requests', unit: 'count', color: '#3b82f6' },
          { ts: rdsCpu, label: 'RDS CPU', unit: '%', color: '#14b8a6' },
          { ts: rdsConn, label: 'RDS Connections', unit: 'count', color: '#8b5cf6' },
          { ts: albP99, label: 'p99 Latency', unit: 's', color: '#ef4444' },
        ];
        for (const card of cards) {
          if (!card.ts) continue;
          const trend = computeTrend(card.ts.values);
          metricSummaries.push({
            label: card.label,
            value: fmtValue(card.ts.latest, card.unit),
            unit: card.unit === '%' ? '%' : card.unit === 's' ? 'ms/s' : card.unit,
            sparklineData: card.ts.values,
            color: card.color,
            ...trend,
          });
        }
      } else {
        // Fallback: use reranker/DB stats when CloudWatch is unavailable
        if (stats) {
          const totalRequests = stats.cache_hits + stats.cache_misses;
          const hitRate = totalRequests > 0 ? (stats.cache_hits / totalRequests) * 100 : 0;
          metricSummaries.push(
            { label: 'Cache Hit Rate', value: `${hitRate.toFixed(1)}%`, unit: '%' },
            { label: 'Cache Size', value: stats.cache_size, unit: 'items' },
            { label: 'Total Requests', value: totalRequests, unit: 'requests' },
          );
        }
        if (databaseStats && !databaseStats.error) {
          metricSummaries.push(
            { label: 'DB Connections', value: `${databaseStats.active_connections || 0}/${databaseStats.max_connections || 100}`, unit: 'active' },
            { label: 'Queue Size', value: databaseStats.queue_size || 0, unit: 'chunks' },
          );
        }
      }

      // Calculate cost breakdown (placeholder - would need actual cost data)
      const costBreakdown: CostBreakdown[] = [];

      // Legacy flat metrics (kept for backward compat)
      const cloudWatchMetrics: CloudWatchMetric[] = [];

      setData({
        cloudWatchMetrics,
        rerankerStats: stats,
        databaseStats: databaseStats && !databaseStats.error ? databaseStats : null,
        serviceHealth,
        metricSummaries,
        costBreakdown,
      });
      setLastUpdated(new Date());

      // Detect maintenance mode: all core services unhealthy = system updating
      const coreServices = serviceHealth.filter(s =>
        s.name === 'Agent Service' || s.name === 'PostgreSQL'
      );
      const allCoreDown = coreServices.length > 0 && coreServices.every(s => s.status === 'unhealthy');
      const skipMaintenance = process.env.NEXT_PUBLIC_DISABLE_MAINTENANCE === 'true';
      setIsMaintenanceMode(skipMaintenance ? false : allCoreDown);
    } catch (error) {
      console.error('Error refreshing observability data:', error);
      // All fetches failed = likely maintenance
      const skipMaintenance = process.env.NEXT_PUBLIC_DISABLE_MAINTENANCE === 'true';
      setIsMaintenanceMode(skipMaintenance ? false : true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial data fetch
  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(refreshData, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [refreshData]);

  // Get metrics by namespace
  const getMetricsByNamespace = useCallback((namespace: string) => {
    return data.cloudWatchMetrics.filter(m => m.namespace === namespace);
  }, [data.cloudWatchMetrics]);

  // Get overall health status
  const getOverallHealth = useCallback((): 'healthy' | 'degraded' | 'unhealthy' => {
    if (data.serviceHealth.some(s => s.status === 'unhealthy')) return 'unhealthy';
    if (data.serviceHealth.some(s => s.status === 'degraded')) return 'degraded';
    return 'healthy';
  }, [data.serviceHealth]);

  // Calculate cache hit rate
  const getCacheHitRate = useCallback((): number => {
    if (!data.rerankerStats) return 0;
    const total = data.rerankerStats.cache_hits + data.rerankerStats.cache_misses;
    return total > 0 ? (data.rerankerStats.cache_hits / total) * 100 : 0;
  }, [data.rerankerStats]);

  // Get total estimated cost
  const getTotalCost = useCallback((): number => {
    return data.costBreakdown.reduce((sum, item) => sum + item.cost, 0);
  }, [data.costBreakdown]);

  return {
    cloudWatchMetrics: data.cloudWatchMetrics,
    rerankerStats: data.rerankerStats,
    databaseStats: data.databaseStats,
    serviceHealth: data.serviceHealth,
    metricSummaries: data.metricSummaries,
    costBreakdown: data.costBreakdown,
    isLoading,
    isMaintenanceMode,
    lastUpdated,
    refreshData,
    getMetricsByNamespace,
    getOverallHealth,
    getCacheHitRate,
    getTotalCost,
  };
}
