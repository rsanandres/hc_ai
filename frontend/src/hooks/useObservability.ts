'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getMockCloudWatchMetrics,
  getMockLangSmithTraces,
  getMockRerankerStats,
  getMockServiceHealth,
  getMockMetricSummaries,
  getMockCostBreakdown,
} from '@/services/mockData';

const REFRESH_INTERVAL = 30000; // 30 seconds (mock data doesn't need frequent updates)

// Initial data fetch (synchronous for initial render)
function getInitialData() {
  return {
    cloudWatchMetrics: getMockCloudWatchMetrics(),
    langSmithTraces: getMockLangSmithTraces(10),
    rerankerStats: getMockRerankerStats(),
    serviceHealth: getMockServiceHealth(),
    metricSummaries: getMockMetricSummaries(),
    costBreakdown: getMockCostBreakdown(),
  };
}

export function useObservability() {
  // Initialize with data to avoid calling setState in effect
  const [data, setData] = useState(getInitialData);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const refreshData = useCallback(() => {
    setIsLoading(true);
    // Using mock data - replace with real API calls later
    setData({
      cloudWatchMetrics: getMockCloudWatchMetrics(),
      langSmithTraces: getMockLangSmithTraces(10),
      rerankerStats: getMockRerankerStats(),
      serviceHealth: getMockServiceHealth(),
      metricSummaries: getMockMetricSummaries(),
      costBreakdown: getMockCostBreakdown(),
    });
    setLastUpdated(new Date());
    setIsLoading(false);
  }, []);

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
    langSmithTraces: data.langSmithTraces,
    rerankerStats: data.rerankerStats,
    serviceHealth: data.serviceHealth,
    metricSummaries: data.metricSummaries,
    costBreakdown: data.costBreakdown,
    isLoading,
    lastUpdated,
    refreshData,
    getMetricsByNamespace,
    getOverallHealth,
    getCacheHitRate,
    getTotalCost,
  };
}
