'use client';

import { Box, Typography, IconButton, Tooltip, Grid, alpha, Skeleton } from '@mui/material';
import { motion } from 'framer-motion';
import { Activity, RefreshCw } from 'lucide-react';
import { ServiceHealth } from '@/types';
import { MetricSummary } from '@/types/observability';
import { HealthIndicator } from './HealthIndicator';
import { MetricsCard } from './MetricsCard';
import { glassStyle } from '@/theme/theme';

interface ObservabilityPanelProps {
  serviceHealth: ServiceHealth[];
  metricSummaries: MetricSummary[];
  lastUpdated: Date;
  onRefresh: () => void;
  isLoading: boolean;
}

export function ObservabilityPanel({
  serviceHealth,
  metricSummaries,
  lastUpdated,
  onRefresh,
  isLoading,
}: ObservabilityPanelProps) {
  // Get overall health status
  const overallHealth = serviceHealth.some(s => s.status === 'unhealthy') ? 'unhealthy' :
                        serviceHealth.some(s => s.status === 'degraded') ? 'degraded' : 'healthy';

  const healthColor = overallHealth === 'healthy' ? 'success.main' :
                      overallHealth === 'degraded' ? 'warning.main' : 'error.main';


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


          </>
          )}
        </Box>
      </Box>
    </div>
  );
}
