'use client';

import { memo } from 'react';
import { Box, Typography, Tooltip, alpha } from '@mui/material';
import { ServiceHealth } from '@/types';

const STATUS_COLORS = {
  healthy: '#22c55e',
  degraded: '#f59e0b',
  unhealthy: '#ef4444',
};

interface HealthIndicatorProps {
  service: ServiceHealth;
}

export const HealthIndicator = memo(function HealthIndicator({ service }: HealthIndicatorProps) {
  const color = STATUS_COLORS[service.status];

  return (
    <Tooltip
      title={
        <Box>
          <Typography variant="caption" display="block">
            {service.name}
          </Typography>
          <Typography variant="caption" display="block" color="text.secondary">
            Status: {service.status}
          </Typography>
          {service.latency && (
            <Typography variant="caption" display="block" color="text.secondary">
              Latency: {service.latency}ms
            </Typography>
          )}
        </Box>
      }
      arrow
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1,
          py: 0.5,
          borderRadius: '6px',
          bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
          cursor: 'pointer',
          '&:hover': {
            bgcolor: (theme) => alpha(theme.palette.common.white, 0.05),
          },
          transition: 'background-color 0.2s ease',
        }}
      >
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: color,
            boxShadow: `0 0 8px ${alpha(color, 0.5)}`,
            // CSS animation instead of framer-motion for better performance
            animation: service.status !== 'healthy' ? 'pulse 2s ease-in-out infinite' : 'none',
            '@keyframes pulse': {
              '0%, 100%': { transform: 'scale(1)' },
              '50%': { transform: 'scale(1.2)' },
            },
          }}
        />
        <Typography
          variant="caption"
          sx={{
            fontWeight: 500,
            color: 'text.secondary',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: 100,
          }}
        >
          {service.name.replace(' Service', '')}
        </Typography>
      </Box>
    </Tooltip>
  );
});
