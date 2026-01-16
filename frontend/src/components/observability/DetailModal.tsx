'use client';

import { Box, Typography, Modal, IconButton, Divider, Grid, alpha } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Activity, DollarSign, Zap, Database } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, PieChart, Pie, Cell } from 'recharts';
import { ServiceHealth } from '@/types';
import { CloudWatchMetric, LangSmithTrace, CostBreakdown } from '@/types/observability';
import { HealthIndicator } from './HealthIndicator';
import { glassStyle } from '@/theme/theme';

interface DetailModalProps {
  open: boolean;
  onClose: () => void;
  serviceHealth: ServiceHealth[];
  cloudWatchMetrics: CloudWatchMetric[];
  langSmithTraces: LangSmithTrace[];
  costBreakdown: CostBreakdown[];
}

const COLORS = ['#14b8a6', '#8b5cf6', '#f59e0b', '#64748b'];

export function DetailModal({
  open,
  onClose,
  serviceHealth,
  cloudWatchMetrics,
  langSmithTraces,
  costBreakdown,
}: DetailModalProps) {
  // Prepare latency data for bar chart
  const latencyData = cloudWatchMetrics
    .filter(m => m.metricName.toLowerCase().includes('latency'))
    .map(m => ({
      name: m.dimensions[0]?.value?.replace('hcai-', '') || m.namespace.split('/')[1],
      latency: Math.round(m.value),
    }));

  // Calculate totals for traces
  const totalTokens = langSmithTraces.reduce((sum, t) => sum + (t.tokenUsage?.total || 0), 0);
  const avgLatency = langSmithTraces.length > 0
    ? Math.round(langSmithTraces.reduce((sum, t) => sum + t.latencyMs, 0) / langSmithTraces.length)
    : 0;
  const errorCount = langSmithTraces.filter(t => t.status === 'error').length;

  return (
    <Modal open={open} onClose={onClose}>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '90%',
              maxWidth: 900,
              maxHeight: '90vh',
              overflow: 'auto',
            }}
          >
            <Box
              sx={{
                borderRadius: '20px',
                p: 3,
                ...glassStyle,
                bgcolor: 'background.paper',
              }}
            >
              {/* Header */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 600 }}>
                    System Observability
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Real-time infrastructure metrics and traces
                  </Typography>
                </Box>
                <IconButton onClick={onClose}>
                  <X size={20} />
                </IconButton>
              </Box>

              {/* Service Health Row */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
                  Service Health
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {serviceHealth.map((service, idx) => (
                    <HealthIndicator key={idx} service={service} />
                  ))}
                </Box>
              </Box>

              <Divider sx={{ mb: 3 }} />

              <Grid container spacing={3}>
                {/* Latency Chart */}
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: '12px',
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <Zap size={16} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        Latency by Service
                      </Typography>
                    </Box>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={latencyData}>
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{
                            background: '#1a1a24',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: 8,
                          }}
                        />
                        <Bar dataKey="latency" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                </Grid>

                {/* Cost Breakdown */}
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: '12px',
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <DollarSign size={16} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        Cost Breakdown (Monthly Est.)
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <ResponsiveContainer width={120} height={120}>
                        <PieChart>
                          <Pie
                            data={costBreakdown}
                            dataKey="cost"
                            nameKey="service"
                            cx="50%"
                            cy="50%"
                            innerRadius={35}
                            outerRadius={50}
                          >
                            {costBreakdown.map((entry, index) => (
                              <Cell key={entry.service} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                      <Box sx={{ flex: 1 }}>
                        {costBreakdown.map((item, idx) => (
                          <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: COLORS[idx % COLORS.length] }} />
                            <Typography variant="caption" sx={{ flex: 1 }}>
                              {item.service}
                            </Typography>
                            <Typography variant="caption" sx={{ fontWeight: 600 }}>
                              ${item.cost.toFixed(2)}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Box>
                  </Box>
                </Grid>

                {/* Trace Summary */}
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: '12px',
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <Activity size={16} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        LangSmith Traces (Last Hour)
                      </Typography>
                    </Box>
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 4 }}>
                        <Typography variant="caption" color="text.secondary">Total Traces</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>{langSmithTraces.length}</Typography>
                      </Grid>
                      <Grid size={{ xs: 4 }}>
                        <Typography variant="caption" color="text.secondary">Avg Latency</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>{avgLatency}ms</Typography>
                      </Grid>
                      <Grid size={{ xs: 4 }}>
                        <Typography variant="caption" color="text.secondary">Errors</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 600, color: errorCount > 0 ? 'error.main' : 'success.main' }}>
                          {errorCount}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                </Grid>

                {/* Token Usage */}
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: '12px',
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <Database size={16} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        Token Usage (Last Hour)
                      </Typography>
                    </Box>
                    <Typography variant="h4" sx={{ fontWeight: 600, color: 'primary.main' }}>
                      {(totalTokens / 1000).toFixed(1)}K
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Estimated cost: ${((totalTokens / 1000) * 0.0015).toFixed(3)}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </Modal>
  );
}
