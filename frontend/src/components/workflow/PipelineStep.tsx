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
  value: string | number;
  icon?: React.ElementType;
  highlight?: boolean;
}

interface PipelineStepProps {
  step: PipelineStepType;
  isLast: boolean;
  queryText?: string;
  details?: Record<string, unknown>;
}

// Generate mock details based on step type
function getStepDetails(stepId: string, queryText?: string, details?: Record<string, unknown>): StepDetail[] {
  switch (stepId) {
    case 'query':
      return [
        { label: 'Query', value: queryText ? `"${queryText.slice(0, 50)}${queryText.length > 50 ? '...' : ''}"` : 'Waiting...', icon: MessageSquare },
        { label: 'Characters', value: queryText?.length || 0, icon: Hash },
      ];
    case 'pii_mask':
      return [
        { label: 'Entities Found', value: details?.entitiesFound ?? Math.floor(Math.random() * 5) + 1, icon: Eye },
        { label: 'Names Masked', value: details?.namesMasked ?? Math.floor(Math.random() * 2), icon: EyeOff },
        { label: 'IDs Masked', value: details?.idsMasked ?? Math.floor(Math.random() * 3) + 1, icon: EyeOff },
        { label: 'Dates Masked', value: details?.datesMasked ?? Math.floor(Math.random() * 2), icon: EyeOff },
        { label: 'Processing Time', value: `${details?.processingTime ?? Math.floor(Math.random() * 50) + 10}ms`, icon: Clock },
      ];
    case 'vector_search':
      return [
        { label: 'Collection', value: 'fhir_chunks', icon: Database },
        { label: 'Documents Retrieved', value: details?.docsRetrieved ?? Math.floor(Math.random() * 30) + 20, icon: FileText, highlight: true },
        { label: 'Search Time', value: `${details?.searchTime ?? Math.floor(Math.random() * 100) + 50}ms`, icon: Clock },
        { label: 'Embedding Model', value: 'Amazon Titan v2', icon: Zap },
      ];
    case 'rerank':
      return [
        { label: 'Candidates In', value: details?.candidatesIn ?? Math.floor(Math.random() * 30) + 20, icon: FileText },
        { label: 'Results Out', value: details?.resultsOut ?? 10, icon: FileText, highlight: true },
        { label: 'Top Score', value: (details?.topScore ?? (Math.random() * 0.3 + 0.7)).toFixed(3), icon: Zap },
        { label: 'Model', value: 'MiniLM-L6-v2', icon: Brain },
        { label: 'Rerank Time', value: `${details?.rerankTime ?? Math.floor(Math.random() * 200) + 100}ms`, icon: Clock },
      ];
    case 'llm_react':
      return [
        { label: 'Model', value: 'Claude 3.5 Haiku', icon: Brain },
        { label: 'Input Tokens', value: details?.inputTokens ?? Math.floor(Math.random() * 1500) + 500, icon: Hash },
        { label: 'Output Tokens', value: details?.outputTokens ?? Math.floor(Math.random() * 400) + 100, icon: Hash },
        { label: 'Reasoning Steps', value: details?.reasoningSteps ?? Math.floor(Math.random() * 3) + 1, icon: Zap, highlight: true },
        { label: 'Tools Invoked', value: details?.toolsInvoked ?? Math.floor(Math.random() * 3) + 1, icon: Layers },
        { label: 'Latency', value: `${details?.latency ?? Math.floor(Math.random() * 2000) + 800}ms`, icon: Clock },
      ];
    case 'response':
      return [
        { label: 'Response Length', value: `${details?.responseLength ?? Math.floor(Math.random() * 300) + 100} chars`, icon: Hash },
        { label: 'Sources Cited', value: details?.sourcesCited ?? Math.floor(Math.random() * 5) + 1, icon: FileText, highlight: true },
        { label: 'PII Re-masked', value: details?.piiRemasked ?? Math.floor(Math.random() * 2), icon: EyeOff },
        { label: 'Total Latency', value: `${details?.totalLatency ?? Math.floor(Math.random() * 3000) + 1500}ms`, icon: Clock },
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

  const stepDetails = getStepDetails(step.id, queryText, details);

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
                      color: detail.highlight ? 'primary.main' : 'text.primary',
                      fontFamily: typeof detail.value === 'number' ? 'var(--font-geist-mono)' : 'inherit',
                    }}
                  >
                    {detail.value}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        </Collapse>

        {step.duration && !expanded && (
          <Typography
            variant="caption"
            sx={{ color: 'success.main', fontWeight: 500, ml: canExpand ? 2.5 : 0 }}
          >
            {step.duration}ms
          </Typography>
        )}
      </Box>
    </Box>
  );
}
