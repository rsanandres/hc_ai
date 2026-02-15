'use client';

import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Button, IconButton, alpha, useTheme, useMediaQuery } from '@mui/material';
import { X, ChevronRight, ChevronLeft, MessageSquare, Workflow, Activity, Users, Bug, Clock, FileText } from 'lucide-react';

const STORAGE_KEY = 'hcai-tour-completed';

interface TourStep {
  title: string;
  description: string;
  icon: React.ElementType;
  target: string | null; // data-tour attribute selector, null = no spotlight
}

const TOUR_STEPS: TourStep[] = [
  {
    title: 'Chat Panel',
    description: 'Ask medical questions in natural language. The AI agent will search clinical records and reason through the data to answer.',
    icon: MessageSquare,
    target: 'chat',
  },
  {
    title: 'A Note on Performance',
    description: 'This is a portfolio project, so responses may take a moment. To keep costs reasonable I opted for smaller infrastructure, but there are clear improvements I could make with additional investment (larger instances, vector indexing, caching).',
    icon: Clock,
    target: null,
  },
  {
    title: 'Reference Panel',
    description: 'Browse featured patients, switch between patients, and pick from recommended questions.',
    icon: Users,
    target: 'workflow',
  },
  {
    title: 'View Patient Data',
    description: 'Click the document icon next to a patient\'s name — in the sidebar or the chat header — to browse their full FHIR record: conditions, medications, labs, encounters, and raw JSON.',
    icon: FileText,
    target: 'chat',
  },
  {
    title: 'Pipeline View',
    description: 'Watch your query flow through the RAG pipeline in real time: PII masking, vector search, LLM reasoning, and response synthesis.',
    icon: Workflow,
    target: 'workflow',
  },
  {
    title: 'Observability Panel',
    description: 'Monitor system health, CloudWatch metrics, and service status. You\'re in debug mode by default to see the agent\'s internals.',
    icon: Activity,
    target: 'observability',
  },
  {
    title: 'Debug Mode',
    description: 'Debug mode is on by default so you can see every step the agent takes. Toggle it off anytime with the bug icon in the chat header.',
    icon: Bug,
    target: 'chat',
  },
];

interface OnboardingTourProps {
  forceShow?: boolean;
  onDismiss?: () => void;
}

interface SpotlightRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export function OnboardingTour({ forceShow, onDismiss }: OnboardingTourProps) {
  const [visible, setVisible] = useState(!!forceShow);
  const [canDismiss, setCanDismiss] = useState(false);
  const [step, setStep] = useState(0);
  const [spotlight, setSpotlight] = useState<SpotlightRect | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ top?: number; left?: number; bottom?: number } | null>(null);
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

  // Show tour every visit so repeat visitors and demo audiences always see it
  useEffect(() => {
    if (forceShow) return;
    const timer = setTimeout(() => setVisible(true), 1000);
    return () => clearTimeout(timer);
  }, [forceShow]);

  // React to forceShow changes (e.g., help button clicked)
  useEffect(() => {
    if (forceShow) {
      setStep(0);
      setVisible(true);
      // Delay enabling dismiss so the triggering click doesn't immediately close the tour
      setCanDismiss(false);
      const timer = setTimeout(() => setCanDismiss(true), 300);
      return () => clearTimeout(timer);
    }
  }, [forceShow]);

  // Enable dismiss after tour first appears (auto-show path)
  useEffect(() => {
    if (visible && !canDismiss) {
      const timer = setTimeout(() => setCanDismiss(true), 300);
      return () => clearTimeout(timer);
    }
  }, [visible, canDismiss]);

  const computePositions = useCallback(() => {
    if (!visible) return;

    const current = TOUR_STEPS[step];
    const padding = 8;
    const tooltipWidth = 420;
    const tooltipHeight = 220;
    const gap = 16;

    if (!current.target || !isDesktop) {
      setSpotlight(null);
      setTooltipPos(null);
      return;
    }

    const target = document.querySelector(`[data-tour="${current.target}"]`) as HTMLElement;
    if (!target) {
      setSpotlight(null);
      setTooltipPos(null);
      return;
    }

    const rect = target.getBoundingClientRect();

    // Spotlight rect (slightly padded around target)
    setSpotlight({
      top: rect.top - padding,
      left: rect.left - padding,
      width: rect.width + padding * 2,
      height: rect.height + padding * 2,
    });

    // Position tooltip beside the target element
    const elementCenterX = rect.left + rect.width / 2;
    const isOnRight = elementCenterX > window.innerWidth / 2;

    let top: number;
    let left: number;

    if (isOnRight) {
      left = rect.left - tooltipWidth - gap;
      top = rect.top + rect.height / 2 - tooltipHeight / 2;
    } else {
      left = rect.right + gap;
      top = rect.top + rect.height / 2 - tooltipHeight / 2;
    }

    // If beside doesn't fit, try below
    if (left < 16 || left + tooltipWidth > window.innerWidth - 16) {
      left = Math.max(16, rect.left + rect.width / 2 - tooltipWidth / 2);
      left = Math.min(left, window.innerWidth - tooltipWidth - 16);
      top = rect.bottom + gap;
    }

    // Constrain to viewport
    top = Math.max(16, Math.min(top, window.innerHeight - tooltipHeight - 16));
    left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16));

    setTooltipPos({ top, left });
  }, [step, visible, isDesktop]);

  // Recalculate on step change and window resize
  useEffect(() => {
    computePositions();
    window.addEventListener('resize', computePositions);
    return () => window.removeEventListener('resize', computePositions);
  }, [computePositions]);

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(STORAGE_KEY, 'true');
    onDismiss?.();
  };

  const next = () => {
    if (step < TOUR_STEPS.length - 1) setStep(step + 1);
    else dismiss();
  };

  const prev = () => {
    if (step > 0) setStep(step - 1);
  };

  if (!visible) return null;

  const current = TOUR_STEPS[step];
  const Icon = current.icon;
  const isLast = step === TOUR_STEPS.length - 1;

  // Tooltip positioning: use calculated position or fall back to centered bottom
  const tooltipStyle: React.CSSProperties = tooltipPos
    ? {
        position: 'fixed',
        top: tooltipPos.top,
        left: tooltipPos.left,
        zIndex: 10000,
        width: '90%',
        maxWidth: 420,
      }
    : {
        position: 'fixed',
        bottom: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10000,
        width: '90%',
        maxWidth: 460,
      };

  return (
    <>
      {/* Click-away layer — only active after canDismiss delay */}
      <div
        onClick={canDismiss ? dismiss : undefined}
        style={{ position: 'fixed', inset: 0, zIndex: 9997 }}
      />

      {/* Spotlight overlay: darkens everything except the target element */}
      {spotlight ? (
        <div
          style={{
            position: 'fixed',
            top: spotlight.top,
            left: spotlight.left,
            width: spotlight.width,
            height: spotlight.height,
            borderRadius: 16,
            boxShadow: '0 0 0 9999px rgba(0,0,0,0.5)',
            zIndex: 9998,
            pointerEvents: 'none',
            transition: 'top 0.3s, left 0.3s, width 0.3s, height 0.3s',
          }}
        />
      ) : (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9998,
            backgroundColor: 'rgba(0,0,0,0.5)',
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Tour card — onClick stopPropagation prevents the click-away layer from catching clicks inside the card */}
      <div style={tooltipStyle} onClick={(e) => e.stopPropagation()}>
        <Box
          sx={{
            bgcolor: alpha(theme.palette.background.paper, 0.95),
            backdropFilter: 'blur(20px)',
            borderRadius: '16px',
            border: '1px solid',
            borderColor: alpha(theme.palette.primary.main, 0.2),
            p: 3,
            boxShadow: `0 20px 60px ${alpha(theme.palette.common.black, 0.4)}`,
          }}
        >
          {/* Close button */}
          <IconButton
            onClick={dismiss}
            size="small"
            sx={{ position: 'absolute', top: 8, right: 8, color: 'text.disabled' }}
          >
            <X size={16} />
          </IconButton>

          {/* Step indicator */}
          <Box sx={{ display: 'flex', gap: 0.5, mb: 2 }}>
            {TOUR_STEPS.map((_, i) => (
              <Box
                key={i}
                sx={{
                  height: 3,
                  flex: 1,
                  borderRadius: 2,
                  bgcolor: i <= step
                    ? 'primary.main'
                    : alpha(theme.palette.text.disabled, 0.2),
                  transition: 'background-color 0.3s',
                }}
              />
            ))}
          </Box>

          {/* Content */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: '10px',
                bgcolor: alpha(theme.palette.primary.main, 0.15),
                color: 'primary.main',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Icon size={20} />
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
                {current.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>
                {current.description}
              </Typography>
            </Box>
          </Box>

          {/* Navigation */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 2.5 }}>
            <Typography variant="caption" color="text.disabled">
              {step + 1} of {TOUR_STEPS.length}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              {step > 0 && (
                <Button
                  size="small"
                  onClick={prev}
                  startIcon={<ChevronLeft size={14} />}
                  sx={{ textTransform: 'none', color: 'text.secondary' }}
                >
                  Back
                </Button>
              )}
              <Button
                size="small"
                variant="contained"
                onClick={next}
                endIcon={!isLast ? <ChevronRight size={14} /> : undefined}
                sx={{ textTransform: 'none', minWidth: 80 }}
              >
                {isLast ? 'Got it!' : 'Next'}
              </Button>
            </Box>
          </Box>
        </Box>
      </div>
    </>
  );
}
