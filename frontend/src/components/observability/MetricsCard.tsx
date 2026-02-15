'use client';

import { memo, useMemo } from 'react';
import { Box, Typography, Tooltip, alpha } from '@mui/material';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { AreaChart, Area } from 'recharts';
import { MetricSummary } from '@/types/observability';

interface MetricsCardProps {
  metric: MetricSummary;
  index: number;
}

// Memoized sparkline to prevent re-renders
const Sparkline = memo(function Sparkline({ data, index, color = '#14b8a6' }: { data: number[]; index: number; color?: string }) {
  const chartData = useMemo(() => data.map((value, i) => ({ value, index: i })), [data]);

  return (
    <Box sx={{ width: 50, height: 24, opacity: 0.7 }}>
      <AreaChart width={50} height={24} data={chartData}>
        <defs>
          <linearGradient id={`gradient-${index}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#gradient-${index})`}
          isAnimationActive={false}
        />
      </AreaChart>
    </Box>
  );
});

const METRIC_TOOLTIPS: Record<string, string> = {
  'ECS CPU': 'CPU utilization of the ECS Fargate task running the backend API',
  'ECS Memory': 'Memory utilization of the ECS Fargate task',
  'ALB Requests': 'Total HTTP requests hitting the Application Load Balancer',
  'RDS CPU': 'CPU utilization of the PostgreSQL RDS instance',
  'RDS Connections': 'Active database connections to the RDS instance',
  'p99 Latency': '99th percentile response time through the ALB',
  'Cache Hit Rate': 'Percentage of reranker requests served from cache',
  'Cache Size': 'Number of items currently in the reranker cache',
  'Total Requests': 'Total reranker requests (cache hits + misses)',
};

export const MetricsCard = memo(function MetricsCard({ metric, index }: MetricsCardProps) {
  const changeIcon = metric.changeType === 'increase' ? TrendingUp :
                     metric.changeType === 'decrease' ? TrendingDown : Minus;
  const ChangeIcon = changeIcon;

  const changeColor = 'text.secondary';
  const tooltip = METRIC_TOOLTIPS[metric.label] || metric.label;

  return (
    <Tooltip title={tooltip} arrow placement="top" enterDelay={300}>
    <Box
      sx={{
        p: 1.5,
        borderRadius: '10px',
        bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
        border: '1px solid',
        borderColor: 'divider',
        '&:hover': {
          bgcolor: (theme) => alpha(theme.palette.common.white, 0.04),
          borderColor: (theme) => alpha(theme.palette.primary.main, 0.2),
        },
        transition: 'all 0.2s ease',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
          {metric.label}
        </Typography>
        {metric.change !== undefined && Math.abs(metric.change) <= 100 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            <ChangeIcon size={10} color={changeColor} />
            <Typography variant="caption" sx={{ color: changeColor, fontWeight: 500, fontSize: '0.65rem' }}>
              {Math.abs(metric.change).toFixed(1)}%
            </Typography>
          </Box>
        )}
      </Box>
      
      <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, lineHeight: 1, mb: 0.25 }}>
            {metric.value}
          </Typography>
          {metric.unit && (
            <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.65rem' }}>
              {metric.unit}
            </Typography>
          )}
        </Box>
        
        {metric.sparklineData && metric.sparklineData.length > 0 && (
          <Sparkline data={metric.sparklineData} index={index} color={metric.color} />
        )}
      </Box>
    </Box>
    </Tooltip>
  );
});
