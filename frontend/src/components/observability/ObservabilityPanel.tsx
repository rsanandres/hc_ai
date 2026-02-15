'use client';

import { Box, Typography, IconButton, Tooltip, Grid, alpha, Divider, Skeleton } from '@mui/material';
import { motion } from 'framer-motion';
import { Activity, RefreshCw, Layers, HardDrive, Database } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip as RechartsTooltip, PieChart, Pie, Cell } from 'recharts';
import { ServiceHealth } from '@/types';
import { MetricSummary, RerankerStats } from '@/types/observability';
import { DatabaseStats } from '@/hooks/useObservability';
import { HealthIndicator } from './HealthIndicator';
import { MetricsCard } from './MetricsCard';
import { glassStyle } from '@/theme/theme';

interface ObservabilityPanelProps {
  serviceHealth: ServiceHealth[];
  metricSummaries: MetricSummary[];
  rerankerStats: RerankerStats | null;
  databaseStats: DatabaseStats | null;
  lastUpdated: Date;
  onRefresh: () => void;
  isLoading: boolean;
}

export function ObservabilityPanel({
  serviceHealth,
  metricSummaries,
  rerankerStats,
  databaseStats,
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

  return (
    <div style={{ height: '100%' }}>
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

          </>
          )}
        </Box>
      </Box>
    </div>
  );
}
