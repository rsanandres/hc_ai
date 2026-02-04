'use client';

import { Box, Typography, alpha, Stack, Chip, LinearProgress } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, CheckCircle, AlertCircle, Wrench, Loader2, MessageSquare } from 'lucide-react';
import { AgentStep } from '@/hooks/useChat';

interface ThinkingPanelProps {
    isVisible: boolean;
    currentStatus: string;
    toolCalls: string[];
    steps: AgentStep[];  // Array of agent steps for timeline display
}

export function ThinkingPanel({
    isVisible,
    currentStatus,
    toolCalls,
    steps,
}: ThinkingPanelProps) {
    if (!isVisible) return null;

    // Helper to get step styling
    const getStepStyle = (step: AgentStep) => {
        switch (step.type) {
            case 'tool_result':
                return {
                    borderColor: '#ff9800',
                    bgColor: alpha('#ff9800', 0.08),
                    textColor: '#ff9800',
                    icon: <Wrench size={12} />,
                    label: `📄 ${step.toolName || 'Tool'} Result`,
                };
            case 'researcher':
                return {
                    borderColor: '#00bcd4',
                    bgColor: alpha('#2c3e50', 0.3),
                    textColor: '#00bcd4',
                    icon: <Brain size={12} />,
                    label: `Researcher (Iteration ${step.iteration})`,
                };
            case 'validator':
                const isApproved = step.result === 'APPROVED';
                return {
                    borderColor: isApproved ? '#4caf50' : '#ff9800',
                    bgColor: alpha(isApproved ? '#4caf50' : '#ff9800', 0.08),
                    textColor: isApproved ? '#4caf50' : '#ff9800',
                    icon: isApproved ? <CheckCircle size={12} /> : <AlertCircle size={12} />,
                    label: `Validator (Iteration ${step.iteration})${step.result ? ` - ${step.result}` : ''}`,
                };
            case 'response':
                return {
                    borderColor: '#9c27b0',
                    bgColor: alpha('#9c27b0', 0.08),
                    textColor: '#9c27b0',
                    icon: <MessageSquare size={12} />,
                    label: 'Response Synthesizer',
                };
        }
    };

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
            >
                <Box
                    sx={{
                        mx: 2,
                        mb: 2,
                        p: 2,
                        borderRadius: '12px',
                        bgcolor: (theme) => alpha(theme.palette.background.paper, 0.6),
                        border: '1px solid',
                        borderColor: 'divider',
                        backdropFilter: 'blur(8px)',
                        maxHeight: '400px',
                        overflow: 'auto',
                    }}
                >
                    <Typography
                        variant="caption"
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                            mb: 1.5,
                            color: 'text.secondary',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                        }}
                    >
                        <Brain size={14} />
                        Agent Thinking ({steps.length} steps)
                    </Typography>

                    <Stack spacing={1.5}>
                        {/* Current Status */}
                        {currentStatus && (
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 1,
                                }}
                            >
                                <motion.div
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                                >
                                    <Loader2 size={14} color="#00bcd4" />
                                </motion.div>
                                <Typography variant="body2" color="info.main">
                                    {currentStatus}
                                </Typography>
                            </Box>
                        )}

                        {/* Tool Calls */}
                        {toolCalls.length > 0 && (
                            <Box>
                                <Typography
                                    variant="caption"
                                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5, color: 'warning.main' }}
                                >
                                    <Wrench size={12} />
                                    Tools Used
                                </Typography>
                                <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5}>
                                    {toolCalls.map((tool, idx) => (
                                        <Chip
                                            key={idx}
                                            label={tool}
                                            size="small"
                                            sx={{
                                                height: 22,
                                                fontSize: '0.7rem',
                                                bgcolor: (theme) => alpha(theme.palette.warning.main, 0.15),
                                                color: 'warning.main',
                                                border: '1px solid',
                                                borderColor: (theme) => alpha(theme.palette.warning.main, 0.3),
                                            }}
                                        />
                                    ))}
                                </Stack>
                            </Box>
                        )}

                        {/* Steps Timeline */}
                        {steps.map((step, idx) => {
                            const style = getStepStyle(step);
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ duration: 0.2, delay: 0.05 }}
                                >
                                    <Box
                                        sx={{
                                            p: 1.5,
                                            borderRadius: '8px',
                                            bgcolor: style.bgColor,
                                            borderLeft: `3px solid ${style.borderColor}`,
                                        }}
                                    >
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: 0.5,
                                                mb: 0.5,
                                                color: style.textColor,
                                                fontWeight: 600,
                                            }}
                                        >
                                            {style.icon}
                                            {style.label}
                                        </Typography>
                                        <Typography
                                            variant="body2"
                                            sx={{
                                                color: 'text.secondary',
                                                fontSize: '0.8rem',
                                                whiteSpace: 'pre-wrap',
                                                maxHeight: '300px',
                                                overflow: 'auto',
                                            }}
                                        >
                                            {step.output}
                                        </Typography>
                                    </Box>
                                </motion.div>
                            );
                        })}

                        {/* Progress indicator when waiting */}
                        {currentStatus && steps.length === 0 && (
                            <LinearProgress
                                sx={{
                                    height: 2,
                                    borderRadius: 1,
                                    bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                                    '& .MuiLinearProgress-bar': {
                                        bgcolor: 'primary.main',
                                    },
                                }}
                            />
                        )}
                    </Stack>
                </Box>
            </motion.div>
        </AnimatePresence>
    );
}
