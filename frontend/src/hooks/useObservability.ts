'use client';

import { useState, useEffect, useCallback } from 'react';
import { ServiceHealth } from '@/types';
import { CloudWatchMetric, LangSmithTrace, MetricSummary, RerankerStats, CostBreakdown } from '@/types/observability';
import {
  getMockCloudWatchMetrics,
  getMockLangSmithTraces,
  getMockRerankerStats,
  getMockServiceHealth,
  getMockMetricSummaries,
  getMockCostBreakdown,
} from '@/services/mockData';

const REFRESH_INTERVAL = 5000; // 5 seconds

export function useObservability() {
  const [cloudWatchMetrics, setCloudWatchMetrics] = useState<CloudWatchMetric[]>([]);
  const [langSmithTraces, setLangSmithTraces] = useState<LangSmithTrace[]>([]);
  const [rerankerStats, setRerankerStats] = useState<RerankerStats | null>(null);
  const [serviceHealth, setServiceHealth] = useState<ServiceHealth[]>([]);
  const [metricSummaries, setMetricSummaries] = useState<MetricSummary[]>([]);
  const [costBreakdown, setCostBreakdown] = useState<CostBreakdown[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const refreshData = useCallback(() => {
    // Using mock data - replace with real API calls later
    setCloudWatchMetrics(getMockCloudWatchMetrics());
    setLangSmithTraces(getMockLangSmithTraces(10));
    setRerankerStats(getMockRerankerStats());
    setServiceHealth(getMockServiceHealth());
    setMetricSummaries(getMockMetricSummaries());
    setCostBreakdown(getMockCostBreakdown());
    setLastUpdated(new Date());
    setIsLoading(false);
  }, []);

  // Initial load
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
    return cloudWatchMetrics.filter(m => m.namespace === namespace);
  }, [cloudWatchMetrics]);

  // Get overall health status
  const getOverallHealth = useCallback((): 'healthy' | 'degraded' | 'unhealthy' => {
    if (serviceHealth.some(s => s.status === 'unhealthy')) return 'unhealthy';
    if (serviceHealth.some(s => s.status === 'degraded')) return 'degraded';
    return 'healthy';
  }, [serviceHealth]);

  // Calculate cache hit rate
  const getCacheHitRate = useCallback((): number => {
    if (!rerankerStats) return 0;
    const total = rerankerStats.cache_hits + rerankerStats.cache_misses;
    return total > 0 ? (rerankerStats.cache_hits / total) * 100 : 0;
  }, [rerankerStats]);

  // Get total estimated cost
  const getTotalCost = useCallback((): number => {
    return costBreakdown.reduce((sum, item) => sum + item.cost, 0);
  }, [costBreakdown]);

  return {
    cloudWatchMetrics,
    langSmithTraces,
    rerankerStats,
    serviceHealth,
    metricSummaries,
    costBreakdown,
    isLoading,
    lastUpdated,
    refreshData,
    getMetricsByNamespace,
    getOverallHealth,
    getCacheHitRate,
    getTotalCost,
  };
}
