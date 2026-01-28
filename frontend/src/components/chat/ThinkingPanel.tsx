'use client';

import { Box, Typography, alpha, Stack, Chip, LinearProgress } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, CheckCircle, AlertCircle, Wrench, Loader2 } from 'lucide-react';

interface ThinkingPanelProps {
    isVisible: boolean;
    currentStatus: string;
    toolCalls: string[];
    researcherOutput: string;
    validatorOutput: string;
    validationResult?: string;
}

export function ThinkingPanel({
    isVisible,
    currentStatus,
    toolCalls,
    researcherOutput,
    validatorOutput,
    validationResult,
}: ThinkingPanelProps) {
    if (!isVisible) return null;

    const hasContent = currentStatus || toolCalls.length > 0 || researcherOutput || validatorOutput;

    return (
        <AnimatePresence>
            {hasContent && (
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
                            Agent Thinking
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

                            {/* Researcher Output */}
                            {researcherOutput && (
                                <Box
                                    sx={{
                                        p: 1.5,
                                        borderRadius: '8px',
                                        bgcolor: alpha('#2c3e50', 0.3),
                                        borderLeft: '3px solid #00bcd4',
                                    }}
                                >
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 0.5,
                                            mb: 0.5,
                                            color: '#00bcd4',
                                            fontWeight: 600,
                                        }}
                                    >
                                        <Brain size={12} />
                                        Researcher
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: 'text.secondary',
                                            fontSize: '0.8rem',
                                            whiteSpace: 'pre-wrap',
                                            maxHeight: '150px',
                                            overflow: 'auto',
                                        }}
                                    >
                                        {researcherOutput.slice(0, 500)}
                                        {researcherOutput.length > 500 && '...'}
                                    </Typography>
                                </Box>
                            )}

                            {/* Validator Output */}
                            {validatorOutput && (
                                <Box
                                    sx={{
                                        p: 1.5,
                                        borderRadius: '8px',
                                        bgcolor: alpha(validationResult === 'APPROVED' ? '#4caf50' : '#ff9800', 0.08),
                                        borderLeft: `3px solid ${validationResult === 'APPROVED' ? '#4caf50' : '#ff9800'}`,
                                    }}
                                >
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 0.5,
                                            mb: 0.5,
                                            color: validationResult === 'APPROVED' ? '#4caf50' : '#ff9800',
                                            fontWeight: 600,
                                        }}
                                    >
                                        {validationResult === 'APPROVED' ? (
                                            <CheckCircle size={12} />
                                        ) : (
                                            <AlertCircle size={12} />
                                        )}
                                        Validator {validationResult ? `(${validationResult})` : ''}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: 'text.secondary',
                                            fontSize: '0.8rem',
                                            whiteSpace: 'pre-wrap',
                                            maxHeight: '150px',
                                            overflow: 'auto',
                                        }}
                                    >
                                        {validatorOutput.slice(0, 500)}
                                        {validatorOutput.length > 500 && '...'}
                                    </Typography>
                                </Box>
                            )}

                            {/* Progress indicator when waiting */}
                            {currentStatus && !researcherOutput && (
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
            )}
        </AnimatePresence>
    );
}
