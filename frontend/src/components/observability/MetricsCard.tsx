'use client';

import { memo, useMemo } from 'react';
import { Box, Typography, alpha } from '@mui/material';
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

export const MetricsCard = memo(function MetricsCard({ metric, index }: MetricsCardProps) {
  const changeIcon = metric.changeType === 'increase' ? TrendingUp :
                     metric.changeType === 'decrease' ? TrendingDown : Minus;
  const ChangeIcon = changeIcon;
  
  const changeColor = metric.changeType === 'increase' ? 'success.main' :
                      metric.changeType === 'decrease' ? 'error.main' : 'text.secondary';

  return (
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
        {metric.change !== undefined && (
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
  );
});
