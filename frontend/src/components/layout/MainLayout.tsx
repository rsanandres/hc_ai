'use client';

import { Box, alpha } from '@mui/material';
import { motion } from 'framer-motion';

interface MainLayoutProps {
  chatPanel: React.ReactNode;
  workflowPanel: React.ReactNode;
  observabilityPanel: React.ReactNode;
  leftActionBar?: React.ReactNode;
}

export function MainLayout({ chatPanel, workflowPanel, observabilityPanel, leftActionBar }: MainLayoutProps) {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background gradient effects */}
      <Box
        sx={{
          position: 'fixed',
          top: '-20%',
          left: '-10%',
          width: '50%',
          height: '50%',
          borderRadius: '50%',
          background: (theme) => `radial-gradient(circle, ${alpha(theme.palette.primary.main, 0.08)} 0%, transparent 60%)`,
          pointerEvents: 'none',
          filter: 'blur(60px)',
        }}
      />
      <Box
        sx={{
          position: 'fixed',
          bottom: '-20%',
          right: '-10%',
          width: '60%',
          height: '60%',
          borderRadius: '50%',
          background: (theme) => `radial-gradient(circle, ${alpha(theme.palette.secondary.main, 0.06)} 0%, transparent 60%)`,
          pointerEvents: 'none',
          filter: 'blur(80px)',
        }}
      />

      {/* Main content */}
      <Box
        sx={{
          position: 'relative',
          zIndex: 1,
          height: '100vh',
          p: 2,
          display: 'flex',
          gap: 2,
        }}
      >
        {/* Left Action Bar (Fixed, persistent) */}
        <Box
          sx={{
            flex: '0 0 56px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            py: 2,
            gap: 2,
            bgcolor: (theme) => alpha(theme.palette.background.paper, 0.5),
            backdropFilter: 'blur(20px)',
            borderRadius: '16px',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          {leftActionBar}
        </Box>

        {/* Left side - Chat (Flex fill) */}
        <motion.div
          style={{ flex: 1, height: '100%', minWidth: 0 }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          {chatPanel}
        </motion.div>

        {/* Right side - Stacked panels (35%) */}
        <Box
          sx={{
            flex: '0 0 32%',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            height: '100%',
          }}
        >
          {/* Top - Workflow (50%) */}
          <Box sx={{ flex: '1 1 50%', minHeight: 0 }}>
            {workflowPanel}
          </Box>

          {/* Bottom - Observability (50%) */}
          <Box sx={{ flex: '1 1 50%', minHeight: 0 }}>
            {observabilityPanel}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
