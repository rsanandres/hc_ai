'use client';

import { Box, Typography, Chip, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import { FileText, Calendar, User } from 'lucide-react';
import { AgentDocument } from '@/types';

interface SourceCardProps {
  source: AgentDocument;
  index: number;
}

export function SourceCard({ source, index }: SourceCardProps) {
  const metadata = source.metadata || {};
  
  // Safely extract metadata values as strings
  const resourceType = metadata.resourceType ? String(metadata.resourceType) : null;
  const effectiveDate = metadata.effectiveDate ? String(metadata.effectiveDate).split('T')[0] : null;
  const patientId = metadata.patientId ? String(metadata.patientId).slice(0, 8) : null;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
    >
      <Box
        sx={{
          p: 1.5,
          borderRadius: '8px',
          bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
          border: '1px solid',
          borderColor: 'divider',
          '&:hover': {
            bgcolor: (theme) => alpha(theme.palette.common.white, 0.04),
            borderColor: (theme) => alpha(theme.palette.primary.main, 0.3),
          },
          transition: 'all 0.2s ease',
          cursor: 'pointer',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
          <Box
            sx={{
              p: 0.5,
              borderRadius: '6px',
              bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
              color: 'primary.main',
            }}
          >
            <FileText size={14} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 500,
                display: 'block',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {source.doc_id}
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                fontSize: '0.7rem',
                lineHeight: 1.4,
              }}
            >
              {source.content_preview}
            </Typography>
          </Box>
        </Box>

        {/* Metadata chips */}
        {(resourceType || effectiveDate || patientId) && (
          <Box sx={{ display: 'flex', gap: 0.5, mt: 1, flexWrap: 'wrap' }}>
            {resourceType && (
              <Chip
                size="small"
                label={resourceType}
                sx={{ height: 18, fontSize: '0.65rem' }}
              />
            )}
            {effectiveDate && (
              <Chip
                size="small"
                icon={<Calendar size={10} />}
                label={effectiveDate}
                sx={{ height: 18, fontSize: '0.65rem', '& .MuiChip-icon': { ml: 0.5 } }}
              />
            )}
            {patientId && (
              <Chip
                size="small"
                icon={<User size={10} />}
                label={patientId}
                sx={{ height: 18, fontSize: '0.65rem', '& .MuiChip-icon': { ml: 0.5 } }}
              />
            )}
          </Box>
        )}
      </Box>
    </motion.div>
  );
}
