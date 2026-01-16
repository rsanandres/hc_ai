'use client';

import { useState } from 'react';
import { Box, Typography, IconButton, Tooltip, Grid, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import { Activity, Maximize2, RefreshCw } from 'lucide-react';
import { ServiceHealth } from '@/types';
import { CloudWatchMetric, LangSmithTrace, MetricSummary, CostBreakdown } from '@/types/observability';
import { HealthIndicator } from './HealthIndicator';
import { MetricsCard } from './MetricsCard';
import { DetailModal } from './DetailModal';
import { glassStyle } from '@/theme/theme';

interface ObservabilityPanelProps {
  serviceHealth: ServiceHealth[];
  metricSummaries: MetricSummary[];
  cloudWatchMetrics: CloudWatchMetric[];
  langSmithTraces: LangSmithTrace[];
  costBreakdown: CostBreakdown[];
  lastUpdated: Date;
  onRefresh: () => void;
  isLoading: boolean;
}

export function ObservabilityPanel({
  serviceHealth,
  metricSummaries,
  cloudWatchMetrics,
  langSmithTraces,
  costBreakdown,
  lastUpdated,
  onRefresh,
  isLoading,
}: ObservabilityPanelProps) {
  const [modalOpen, setModalOpen] = useState(false);

  // Get overall health status
  const overallHealth = serviceHealth.some(s => s.status === 'unhealthy') ? 'unhealthy' :
                        serviceHealth.some(s => s.status === 'degraded') ? 'degraded' : 'healthy';

  const healthColor = overallHealth === 'healthy' ? 'success.main' :
                      overallHealth === 'degraded' ? 'warning.main' : 'error.main';

  return (
    <>
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
            <Box sx={{ display: 'flex', gap: 0.5 }}>
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
              <Tooltip title="Expand details">
                <IconButton
                  size="small"
                  onClick={() => setModalOpen(true)}
                  sx={{ color: 'text.secondary' }}
                >
                  <Maximize2 size={14} />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          {/* Content */}
          <Box sx={{ p: 1.5, flex: 1, overflowY: 'auto' }}>
            {/* Service Health */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'block', color: 'text.secondary' }}>
                Services
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {serviceHealth.slice(0, 4).map((service, idx) => (
                  <HealthIndicator key={idx} service={service} />
                ))}
                {serviceHealth.length > 4 && (
                  <Typography variant="caption" color="text.disabled" sx={{ alignSelf: 'center', ml: 0.5 }}>
                    +{serviceHealth.length - 4}
                  </Typography>
                )}
              </Box>
            </Box>

            {/* Metrics Grid */}
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 1, display: 'block', color: 'text.secondary' }}>
              Metrics
            </Typography>
            <Grid container spacing={1}>
              {metricSummaries.slice(0, 6).map((metric, idx) => (
                <Grid size={{ xs: 6 }} key={idx}>
                  <MetricsCard metric={metric} index={idx} />
                </Grid>
              ))}
            </Grid>
          </Box>
        </Box>
      </motion.div>

      {/* Detail Modal */}
      <DetailModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        serviceHealth={serviceHealth}
        cloudWatchMetrics={cloudWatchMetrics}
        langSmithTraces={langSmithTraces}
        costBreakdown={costBreakdown}
      />
    </>
  );
}
