'use client';

import { useState } from 'react';
import { Box, Typography, Collapse, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  ShieldCheck,
  Database,
  Layers,
  Brain,
  CheckCircle,
  Circle,
  SkipForward,
  Loader2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Zap,
  Hash,
  Eye,
  EyeOff
} from 'lucide-react';
import { PipelineStep as PipelineStepType } from '@/types';

const STEP_ICONS: Record<string, React.ElementType> = {
  query: MessageSquare,
  pii_mask: ShieldCheck,
  vector_search: Database,
  rerank: Layers,
  llm_react: Brain,
  response: CheckCircle,
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'text.disabled',
  active: 'primary.main',
  completed: 'success.main',
  skipped: 'text.disabled',
};

interface StepDetail {
  label: string;
  value: string | number | null;
  icon?: React.ElementType;
  highlight?: boolean;
}

interface PipelineStepProps {
  step: PipelineStepType;
  isLast: boolean;
  queryText?: string;
  details?: Record<string, unknown>;
}

// Helper to get value from details — returns null if value is null/undefined
const getVal = (details: Record<string, unknown> | undefined, key: string): number | null => {
  const val = details?.[key];
  return typeof val === 'number' ? val : null;
};

// Format a numeric value with suffix, or return null if value is null
const fmtMs = (val: number | null): string | null => val !== null ? `${(val / 1000).toFixed(1)}s` : null;
const fmtChars = (val: number | null): string | null => val !== null ? `${val} chars` : null;

// Generate step details using real data where available
function getStepDetails(stepId: string, queryText?: string, details?: Record<string, unknown>): StepDetail[] {
  switch (stepId) {
    case 'query':
      return [
        { label: 'Query', value: queryText ? `"${queryText.slice(0, 50)}${queryText.length > 50 ? '...' : ''}"` : 'Waiting...', icon: MessageSquare },
        { label: 'Characters', value: queryText?.length || 0, icon: Hash },
      ];
    case 'pii_mask':
      return [
        { label: 'Provider', value: 'AWS Comprehend Medical', icon: ShieldCheck },
        { label: 'Action', value: 'DetectPHI on input query', icon: Eye },
      ];
    case 'vector_search':
      return [
        { label: 'Collection', value: 'atlas_table (pgvector)', icon: Database },  // NOTE: actual DB table is still hc_ai_table — display name only
        { label: 'Documents Retrieved', value: getVal(details, 'docsRetrieved'), icon: FileText, highlight: true },
        { label: 'Search', value: 'Hybrid (BM25 + Semantic)', icon: Zap },
        { label: 'Embedding Model', value: 'Amazon Titan Embed v2', icon: Zap },
      ];
    case 'rerank':
      return [
        { label: 'Results Out', value: getVal(details, 'resultsOut'), icon: FileText, highlight: true },
        { label: 'Strategy', value: 'Auto resource-type filtering', icon: Layers },
      ];
    case 'llm_react':
      return [
        { label: 'Model', value: 'Claude 3.5 Sonnet (Bedrock)', icon: Brain },
        { label: 'Reasoning Steps', value: getVal(details, 'reasoningSteps'), icon: Zap, highlight: true },
        { label: 'Tools Invoked', value: getVal(details, 'toolsInvoked'), icon: Layers },
      ];
    case 'response':
      return [
        { label: 'Synthesizer', value: 'Claude 3.5 Haiku (Bedrock)', icon: Brain },
        { label: 'Response Length', value: fmtChars(getVal(details, 'responseLength')), icon: Hash },
        { label: 'Sources Cited', value: getVal(details, 'sourcesCited'), icon: FileText, highlight: true },
        { label: 'Total Latency', value: fmtMs(getVal(details, 'totalLatency')), icon: Clock },
      ];
    default:
      return [];
  }
}

export function PipelineStep({ step, isLast, queryText, details }: PipelineStepProps) {
  const [expanded, setExpanded] = useState(false);
  const Icon = STEP_ICONS[step.id] || Circle;
  const statusColor = STATUS_COLORS[step.status];
  const isActive = step.status === 'active';
  const isCompleted = step.status === 'completed';
  const isSkipped = step.status === 'skipped';
  const canExpand = isCompleted || isActive;

  // Filter out null non-highlighted values (skip rows with no data unless they're important)
  const stepDetails = getStepDetails(step.id, queryText, details)
    .filter(d => d.value !== null || d.highlight);

  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
      {/* Icon and connector line */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          mr: 1.5,
        }}
      >
        <motion.div
          animate={isActive ? { scale: [1, 1.1, 1] } : {}}
          transition={{ repeat: Infinity, duration: 1.5 }}
        >
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: (theme) => alpha(
                isCompleted ? theme.palette.success.main :
                  isActive ? theme.palette.primary.main :
                    theme.palette.text.disabled,
                isSkipped ? 0.05 : 0.15
              ),
              color: statusColor,
              transition: 'all 0.3s ease',
            }}
          >
            {isActive ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
              >
                <Loader2 size={16} />
              </motion.div>
            ) : isSkipped ? (
              <SkipForward size={14} />
            ) : (
              <Icon size={16} />
            )}
          </Box>
        </motion.div>

        {/* Connector line */}
        {!isLast && (
          <Box
            sx={{
              width: 2,
              minHeight: expanded ? 'auto' : 24,
              height: expanded ? '100%' : 24,
              bgcolor: (theme) => alpha(
                isCompleted ? theme.palette.success.main : theme.palette.divider,
                isCompleted ? 0.5 : 1
              ),
              mt: 0.5,
              borderRadius: 1,
              transition: 'all 0.3s ease',
            }}
          />
        )}
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, pb: isLast ? 0 : 1.5, minWidth: 0 }}>
        {/* Header - clickable to expand */}
        <Box
          onClick={() => canExpand && setExpanded(!expanded)}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            cursor: canExpand ? 'pointer' : 'default',
            '&:hover': canExpand ? {
              '& .expand-icon': {
                color: 'text.primary',
              },
            } : {},
          }}
        >
          {canExpand && (
            <Box
              className="expand-icon"
              sx={{
                color: 'text.disabled',
                transition: 'color 0.2s ease',
                display: 'flex',
              }}
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </Box>
          )}
          <Typography
            variant="body2"
            sx={{
              fontWeight: 500,
              color: isSkipped ? 'text.disabled' : 'text.primary',
              textDecoration: isSkipped ? 'line-through' : 'none',
              transition: 'all 0.2s ease',
            }}
          >
            {step.name}
          </Typography>
        </Box>

        <Typography
          variant="caption"
          sx={{
            color: 'text.secondary',
            display: 'block',
            opacity: isSkipped ? 0.5 : 1,
            ml: canExpand ? 2.5 : 0,
          }}
        >
          {step.description}
        </Typography>

        {/* Expandable details */}
        <Collapse in={expanded} timeout={200}>
          <Box
            sx={{
              mt: 1,
              ml: canExpand ? 2.5 : 0,
              p: 1.5,
              borderRadius: '8px',
              bgcolor: (theme) => alpha(theme.palette.common.white, 0.02),
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            {stepDetails.map((detail, idx) => {
              const DetailIcon = detail.icon;
              return (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    py: 0.5,
                    '&:not(:last-child)': {
                      borderBottom: '1px solid',
                      borderColor: (theme) => alpha(theme.palette.divider, 0.5),
                    },
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {DetailIcon && (
                      <DetailIcon size={12} style={{ opacity: 0.5 }} />
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {detail.label}
                    </Typography>
                  </Box>
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: detail.highlight ? 600 : 400,
                      color: detail.value === null ? 'text.disabled' : detail.highlight ? 'primary.main' : 'text.primary',
                      fontFamily: typeof detail.value === 'number' ? 'var(--font-geist-mono)' : 'inherit',
                    }}
                  >
                    {detail.value ?? '---'}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        </Collapse>

        {step.duration != null && !expanded && (
          <Typography
            variant="caption"
            sx={{ color: 'success.main', fontWeight: 500, ml: canExpand ? 2.5 : 0 }}
          >
            {(step.duration / 1000).toFixed(1)}s
          </Typography>
        )}
      </Box>
    </Box>
  );
}
