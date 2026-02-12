'use client';

import { Box, Typography, IconButton, Tooltip, Grid, alpha, Divider, Skeleton } from '@mui/material';
import { motion } from 'framer-motion';
import { Activity, RefreshCw, Layers, HardDrive, Database, Cloud } from 'lucide-react';
import { BarChart, Bar, AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip as RechartsTooltip, PieChart, Pie, Cell } from 'recharts';
import { ServiceHealth } from '@/types';
import { CloudWatchTimeSeries, LangSmithTrace, MetricSummary, RerankerStats } from '@/types/observability';
import { DatabaseStats } from '@/hooks/useObservability';
import { HealthIndicator } from './HealthIndicator';
import { MetricsCard } from './MetricsCard';
import { glassStyle } from '@/theme/theme';

interface ObservabilityPanelProps {
  serviceHealth: ServiceHealth[];
  metricSummaries: MetricSummary[];
  langSmithTraces: LangSmithTrace[];
  rerankerStats: RerankerStats | null;
  databaseStats: DatabaseStats | null;
  cloudWatchTimeSeries: CloudWatchTimeSeries[];
  lastUpdated: Date;
  onRefresh: () => void;
  isLoading: boolean;
}

// Mini sparkline component for CloudWatch metrics
function Sparkline({ data, color, height = 40 }: { data: number[]; color: string; height?: number }) {
  if (!data.length) return null;
  const chartData = data.map((v, i) => ({ v, i }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id={`grad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#grad-${color.replace('#', '')})`}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ObservabilityPanel({
  serviceHealth,
  metricSummaries,
  langSmithTraces,
  rerankerStats,
  databaseStats,
  cloudWatchTimeSeries,
  lastUpdated,
  onRefresh,
  isLoading,
}: ObservabilityPanelProps) {
  // Get overall health status
  const overallHealth = serviceHealth.some(s => s.status === 'unhealthy') ? 'unhealthy' :
                        serviceHealth.some(s => s.status === 'degraded') ? 'degraded' : 'healthy';

  const healthColor = overallHealth === 'healthy' ? 'success.main' :
                      overallHealth === 'degraded' ? 'warning.main' : 'error.main';

  // Prepare reranker cache data for pie chart
  const cacheData = rerankerStats ? [
    { name: 'Hits', value: rerankerStats.cache_hits, color: '#14b8a6' },
    { name: 'Misses', value: rerankerStats.cache_misses, color: '#f59e0b' },
  ] : [];

  // Prepare database pool data for bar chart
  const poolData = databaseStats ? [
    { name: 'Active', value: databaseStats.active_connections || 0 },
    { name: 'Pool Out', value: databaseStats.pool_checked_out || 0 },
    { name: 'Pool In', value: databaseStats.pool_checked_in || 0 },
    { name: 'Queue', value: databaseStats.queue_size || 0 },
  ] : [];

  // Queue stats for display
  const queueStats = databaseStats?.queue_stats || { queued: 0, processed: 0, failed: 0, retries: 0 };

  // LangSmith stats
  const totalTokens = langSmithTraces.reduce((sum, t) => sum + (t.tokenUsage?.total || 0), 0);
  const avgLatency = langSmithTraces.length > 0
    ? Math.round(langSmithTraces.reduce((sum, t) => sum + t.latencyMs, 0) / langSmithTraces.length)
    : 0;
  const errorCount = langSmithTraces.filter(t => t.status === 'error').length;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      style={{ height: '100%' }}
    >
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          borderRadius: '16px',
          overflow: 'hidden',
          ...glassStyle,
        }}
      >
        {/* Header */}
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                p: 0.75,
                borderRadius: '8px',
                bgcolor: (theme) => alpha(theme.palette.secondary.main, 0.1),
                color: 'secondary.main',
                display: 'flex',
              }}
            >
              <Activity size={16} />
            </Box>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
                  Observability
                </Typography>
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    bgcolor: healthColor,
                  }}
                />
              </Box>
              <Typography variant="caption" color="text.secondary">
                Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Typography>
            </Box>
          </Box>
          <Tooltip title="Refresh">
            <IconButton
              size="small"
              onClick={onRefresh}
              disabled={isLoading}
              sx={{ color: 'text.secondary' }}
            >
              <motion.div
                animate={isLoading ? { rotate: 360 } : {}}
                transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
              >
                <RefreshCw size={14} />
              </motion.div>
            </IconButton>
          </Tooltip>
        </Box>

        {/* Scrollable Content */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 1.5 }}>
          {isLoading && serviceHealth.length === 0 ? (
            /* Loading Skeletons */
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'block', color: 'text.secondary' }}>
                Services
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 2 }}>
                {[1, 2, 3, 4].map(i => (
                  <Skeleton key={i} variant="rounded" width={80} height={28} sx={{ borderRadius: '14px' }} />
                ))}
              </Box>
              <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'block', color: 'text.secondary' }}>
                Metrics
              </Typography>
              <Grid container spacing={1} sx={{ mb: 2 }}>
                {[1, 2, 3, 4].map(i => (
                  <Grid size={{ xs: 6 }} key={i}>
                    <Skeleton variant="rounded" height={72} sx={{ borderRadius: '8px' }} />
                  </Grid>
                ))}
              </Grid>
              <Divider sx={{ my: 2 }} />
              <Skeleton variant="rounded" height={100} sx={{ borderRadius: '8px', mb: 2 }} />
              <Skeleton variant="rounded" height={100} sx={{ borderRadius: '8px' }} />
            </Box>
          ) : (
          <>
          {/* Service Health */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'block', color: 'text.secondary' }}>
              Services
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {serviceHealth.map((service, idx) => (
                <HealthIndicator key={idx} service={service} />
              ))}
            </Box>
          </Box>

          {/* Metrics Grid */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'block', color: 'text.secondary' }}>
              Metrics
            </Typography>
            <Grid container spacing={1}>
              {metricSummaries.map((metric, idx) => (
                <Grid size={{ xs: 6 }} key={idx}>
                  <MetricsCard metric={metric} index={idx} />
                </Grid>
              ))}
            </Grid>
          </Box>

          {/* AWS Infrastructure (hidden when no data) */}
          {cloudWatchTimeSeries.length > 0 && (() => {
            const find = (id: string) => cloudWatchTimeSeries.find(m => m.id === id);
            const ecsCpu = find('ecs_cpu');
            const ecsMem = find('ecs_memory');
            const albReq = find('alb_requests');
            const albP50 = find('alb_p50');
            const albP99 = find('alb_p99');
            const rdsCpu = find('rds_cpu');
            const rdsConn = find('rds_connections');

            const fmt = (v: number | null | undefined, unit: string) => {
              if (v == null) return '--';
              if (unit === '%') return `${v.toFixed(1)}%`;
              if (unit === 's') return v < 1 ? `${(v * 1000).toFixed(0)}ms` : `${v.toFixed(2)}s`;
              if (unit === 'count') return v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${Math.round(v)}`;
              return `${v}`;
            };

            return (
              <>
                <Divider sx={{ my: 2 }} />
                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
                    <Cloud size={12} /> AWS Infrastructure
                  </Typography>
                  <Box
                    sx={{
                      p: 1.5,
                      borderRadius: '8px',
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    {/* ECS */}
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem', fontWeight: 600 }}>
                      ECS Container
                    </Typography>
                    <Grid container spacing={1} sx={{ mb: 1 }}>
                      <Grid size={{ xs: 6 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                          <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>CPU</Typography>
                          <Typography variant="caption" fontWeight={600} sx={{ fontSize: '0.65rem' }}>{fmt(ecsCpu?.latest, '%')}</Typography>
                        </Box>
                        <Sparkline data={ecsCpu?.values ?? []} color="#14b8a6" />
                      </Grid>
                      <Grid size={{ xs: 6 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                          <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>Memory</Typography>
                          <Typography variant="caption" fontWeight={600} sx={{ fontSize: '0.65rem' }}>{fmt(ecsMem?.latest, '%')}</Typography>
                        </Box>
                        <Sparkline data={ecsMem?.values ?? []} color="#8b5cf6" />
                      </Grid>
                    </Grid>

                    {/* ALB */}
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem', fontWeight: 600, mt: 1, display: 'block' }}>
                      ALB Traffic
                    </Typography>
                    <Grid container spacing={1} sx={{ mb: 1 }}>
                      <Grid size={{ xs: 4 }}>
                        <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>Requests</Typography>
                        <Typography variant="caption" fontWeight={600} display="block" sx={{ fontSize: '0.65rem' }}>{fmt(albReq?.latest, 'count')}</Typography>
                        <Sparkline data={albReq?.values ?? []} color="#3b82f6" height={30} />
                      </Grid>
                      <Grid size={{ xs: 4 }}>
                        <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>p50</Typography>
                        <Typography variant="caption" fontWeight={600} display="block" sx={{ fontSize: '0.65rem' }}>{fmt(albP50?.latest, 's')}</Typography>
                        <Sparkline data={albP50?.values ?? []} color="#f59e0b" height={30} />
                      </Grid>
                      <Grid size={{ xs: 4 }}>
                        <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>p99</Typography>
                        <Typography variant="caption" fontWeight={600} display="block" sx={{ fontSize: '0.65rem' }}>{fmt(albP99?.latest, 's')}</Typography>
                        <Sparkline data={albP99?.values ?? []} color="#ef4444" height={30} />
                      </Grid>
                    </Grid>

                    {/* RDS */}
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem', fontWeight: 600, mt: 1, display: 'block' }}>
                      RDS Database
                    </Typography>
                    <Grid container spacing={1}>
                      <Grid size={{ xs: 6 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                          <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>CPU</Typography>
                          <Typography variant="caption" fontWeight={600} sx={{ fontSize: '0.65rem' }}>{fmt(rdsCpu?.latest, '%')}</Typography>
                        </Box>
                        <Sparkline data={rdsCpu?.values ?? []} color="#14b8a6" />
                      </Grid>
                      <Grid size={{ xs: 6 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                          <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>Connections</Typography>
                          <Typography variant="caption" fontWeight={600} sx={{ fontSize: '0.65rem' }}>{fmt(rdsConn?.latest, 'count')}</Typography>
                        </Box>
                        <Sparkline data={rdsConn?.values ?? []} color="#8b5cf6" />
                      </Grid>
                    </Grid>
                  </Box>
                </Box>
              </>
            );
          })()}

          <Divider sx={{ my: 2 }} />

          {/* Reranker Cache */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <Layers size={12} /> Reranker Cache
            </Typography>
            {rerankerStats ? (
              <Box
                sx={{
                  p: 1.5,
                  borderRadius: '8px',
                  bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {cacheData.length > 0 && (rerankerStats.cache_hits > 0 || rerankerStats.cache_misses > 0) ? (
                    <ResponsiveContainer width={80} height={80}>
                      <PieChart>
                        <Pie
                          data={cacheData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={25}
                          outerRadius={35}
                        >
                          {cacheData.map((entry) => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <Box sx={{ width: 80, height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Typography variant="caption" color="text.disabled">No data</Typography>
                    </Box>
                  )}
                  <Box sx={{ flex: 1, fontSize: '0.7rem' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                      <Box sx={{ width: 6, height: 6, borderRadius: '2px', bgcolor: '#14b8a6' }} />
                      <Typography variant="caption" sx={{ flex: 1 }}>Hits</Typography>
                      <Typography variant="caption" fontWeight={600}>{rerankerStats.cache_hits}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                      <Box sx={{ width: 6, height: 6, borderRadius: '2px', bgcolor: '#f59e0b' }} />
                      <Typography variant="caption" sx={{ flex: 1 }}>Misses</Typography>
                      <Typography variant="caption" fontWeight={600}>{rerankerStats.cache_misses}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Typography variant="caption" sx={{ flex: 1 }}>Size</Typography>
                      <Typography variant="caption" fontWeight={600}>{rerankerStats.cache_size}</Typography>
                    </Box>
                  </Box>
                </Box>
              </Box>
            ) : (
              <Typography variant="caption" color="text.disabled">No reranker data</Typography>
            )}
          </Box>

          {/* Database Pool */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <HardDrive size={12} /> Database Pool
            </Typography>
            {databaseStats && poolData.length > 0 ? (
              <Box
                sx={{
                  p: 1.5,
                  borderRadius: '8px',
                  bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <ResponsiveContainer width="100%" height={100}>
                  <BarChart data={poolData}>
                    <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 9 }} width={25} />
                    <RechartsTooltip
                      contentStyle={{
                        background: '#1a1a24',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 6,
                        fontSize: '0.7rem',
                      }}
                    />
                    <Bar dataKey="value" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Typography variant="caption" color="text.disabled">No database data</Typography>
            )}
          </Box>

          {/* Queue Processing */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <Database size={12} /> Queue Processing
            </Typography>
            <Box
              sx={{
                p: 1.5,
                borderRadius: '8px',
                bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Grid container spacing={1}>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Queued</Typography>
                  <Typography variant="body2" fontWeight={600}>{queueStats.queued}</Typography>
                </Grid>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Done</Typography>
                  <Typography variant="body2" fontWeight={600} color="success.main">{queueStats.processed}</Typography>
                </Grid>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Failed</Typography>
                  <Typography variant="body2" fontWeight={600} color={queueStats.failed > 0 ? 'error.main' : 'text.primary'}>
                    {queueStats.failed}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Retries</Typography>
                  <Typography variant="body2" fontWeight={600} color={queueStats.retries > 0 ? 'warning.main' : 'text.primary'}>
                    {queueStats.retries}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          </Box>

          {/* LangSmith Traces */}
          <Box>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <Activity size={12} /> LangSmith Traces
            </Typography>
            <Box
              sx={{
                p: 1.5,
                borderRadius: '8px',
                bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              {langSmithTraces.length > 0 ? (
                <Grid container spacing={1}>
                  <Grid size={{ xs: 4 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Total</Typography>
                    <Typography variant="body2" fontWeight={600}>{langSmithTraces.length}</Typography>
                  </Grid>
                  <Grid size={{ xs: 4 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Avg Latency</Typography>
                    <Typography variant="body2" fontWeight={600}>{avgLatency}ms</Typography>
                  </Grid>
                  <Grid size={{ xs: 4 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Errors</Typography>
                    <Typography variant="body2" fontWeight={600} color={errorCount > 0 ? 'error.main' : 'success.main'}>
                      {errorCount}
                    </Typography>
                  </Grid>
                  {totalTokens > 0 && (
                    <Grid size={{ xs: 12 }}>
                      <Typography variant="caption" color="text.secondary">
                        Tokens: {(totalTokens / 1000).toFixed(1)}K (~${((totalTokens / 1000) * 0.0015).toFixed(3)})
                      </Typography>
                    </Grid>
                  )}
                </Grid>
              ) : (
                <Typography variant="caption" color="text.disabled">
                  No traces. Set LANGSMITH_API_KEY to enable.
                </Typography>
              )}
            </Box>
          </Box>
          </>
          )}
        </Box>
      </Box>
    </motion.div>
  );
}
