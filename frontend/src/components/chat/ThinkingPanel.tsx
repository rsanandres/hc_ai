'use client';

import { useState } from 'react';
import { Box, Typography, alpha, Stack, Chip, LinearProgress, Collapse, IconButton } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, CheckCircle, AlertCircle, Wrench, Loader2, MessageSquare, ChevronDown, ChevronRight, Search, Database, FileText } from 'lucide-react';
import { AgentStep } from '@/hooks/useChat';

interface ThinkingPanelProps {
    isVisible: boolean;
    currentStatus: string;
    toolCalls: string[];
    steps: AgentStep[];  // Array of agent steps for timeline display
}

// Human-readable tool name mapping
const TOOL_LABELS: Record<string, string> = {
    search_clinical_notes: 'Searching clinical notes',
    search_by_resource_type: 'Searching by resource type',
    get_patient_summary: 'Getting patient summary',
    get_patient_timeline: 'Getting patient timeline',
    search_conditions: 'Searching conditions',
    search_medications: 'Searching medications',
    search_observations: 'Searching observations',
    search_lab_results: 'Searching lab results',
    lookup_snomed: 'Looking up SNOMED code',
    lookup_loinc: 'Looking up LOINC code',
    lookup_rxnorm: 'Looking up RxNorm code',
    fda_drug_lookup: 'Looking up FDA drug info',
    fda_drug_interactions: 'Checking drug interactions',
};

// Get the tool icon based on tool name
function getToolIcon(toolName?: string) {
    if (!toolName) return <Wrench size={12} />;
    if (toolName.startsWith('search') || toolName.includes('lookup')) return <Search size={12} />;
    if (toolName.includes('patient') || toolName.includes('timeline')) return <Database size={12} />;
    if (toolName.includes('fda')) return <FileText size={12} />;
    return <Wrench size={12} />;
}

// Format tool call input into a human-readable summary
function formatToolInput(toolName?: string, output?: string): string {
    if (!output) return '';
    try {
        const input = JSON.parse(output);
        const parts: string[] = [];

        // Show the query/search term prominently
        if (input.query) parts.push(`"${input.query}"`);
        if (input.search_query) parts.push(`"${input.search_query}"`);
        if (input.code) parts.push(`Code: ${input.code}`);
        if (input.drug_name) parts.push(`Drug: ${input.drug_name}`);
        if (input.resource_type) parts.push(`Type: ${input.resource_type}`);
        if (input.k) parts.push(`Top ${input.k} results`);

        return parts.length > 0 ? parts.join(' · ') : output;
    } catch {
        return output;
    }
}

// Truncate long tool results for display
function formatToolResult(output: string): string {
    // Count lines/entries to give a summary
    const lines = output.split('\n').filter(l => l.trim());
    if (output.length > 500) {
        const preview = output.slice(0, 400).trim();
        return `${preview}\n\n... (${lines.length} lines total)`;
    }
    return output;
}

// Truncate long LLM outputs
function formatLLMOutput(output: string): string {
    if (output.length > 800) {
        return output.slice(0, 700).trim() + '\n\n... (truncated)';
    }
    return output;
}

function StepCard({ step, idx }: { step: AgentStep; idx: number }) {
    const [expanded, setExpanded] = useState(false);

    const getStepStyle = () => {
        switch (step.type) {
            case 'tool_call':
                return {
                    borderColor: '#2196f3',
                    bgColor: alpha('#2196f3', 0.08),
                    textColor: '#2196f3',
                    icon: getToolIcon(step.toolName),
                    label: TOOL_LABELS[step.toolName || ''] || `Using ${step.toolName || 'tool'}`,
                };
            case 'tool_result':
                return {
                    borderColor: '#ff9800',
                    bgColor: alpha('#ff9800', 0.08),
                    textColor: '#ff9800',
                    icon: <CheckCircle size={12} />,
                    label: `${step.toolName || 'Tool'} returned results`,
                };
            case 'researcher':
                return {
                    borderColor: '#00bcd4',
                    bgColor: alpha('#2c3e50', 0.3),
                    textColor: '#00bcd4',
                    icon: <Brain size={12} />,
                    label: `Researcher (Iteration ${step.iteration})`,
                };
            case 'validator': {
                const isApproved = step.result === 'APPROVED';
                return {
                    borderColor: isApproved ? '#4caf50' : '#ff9800',
                    bgColor: alpha(isApproved ? '#4caf50' : '#ff9800', 0.08),
                    textColor: isApproved ? '#4caf50' : '#ff9800',
                    icon: isApproved ? <CheckCircle size={12} /> : <AlertCircle size={12} />,
                    label: `Validator${step.result ? ` — ${step.result}` : ''}`,
                };
            }
            case 'response':
                return {
                    borderColor: '#9c27b0',
                    bgColor: alpha('#9c27b0', 0.08),
                    textColor: '#9c27b0',
                    icon: <MessageSquare size={12} />,
                    label: 'Generating response',
                };
        }
    };

    const style = getStepStyle();

    // Format the display content based on step type
    const displayContent = (() => {
        switch (step.type) {
            case 'tool_call':
                return formatToolInput(step.toolName, step.output);
            case 'tool_result':
                return formatToolResult(step.output);
            case 'researcher':
            case 'response':
                return formatLLMOutput(step.output);
            case 'validator':
                return formatLLMOutput(step.output);
        }
    })();

    const isLong = step.output.length > 200;

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
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: isLong ? 'pointer' : 'default',
                    }}
                    onClick={() => isLong && setExpanded(!expanded)}
                >
                    <Typography
                        variant="caption"
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                            color: style.textColor,
                            fontWeight: 600,
                        }}
                    >
                        {style.icon}
                        {style.label}
                    </Typography>
                    {isLong && (
                        <IconButton size="small" sx={{ p: 0, color: style.textColor }}>
                            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </IconButton>
                    )}
                </Box>

                {/* Short content always shown */}
                {!isLong && displayContent && (
                    <Typography
                        variant="body2"
                        sx={{
                            color: 'text.secondary',
                            fontSize: '0.8rem',
                            mt: 0.5,
                            whiteSpace: 'pre-wrap',
                        }}
                    >
                        {displayContent}
                    </Typography>
                )}

                {/* Long content collapsible */}
                {isLong && (
                    <Collapse in={expanded} timeout={200}>
                        <Typography
                            variant="body2"
                            sx={{
                                color: 'text.secondary',
                                fontSize: '0.75rem',
                                mt: 0.5,
                                whiteSpace: 'pre-wrap',
                                maxHeight: '300px',
                                overflow: 'auto',
                                fontFamily: step.type === 'tool_result' ? 'monospace' : 'inherit',
                            }}
                        >
                            {displayContent}
                        </Typography>
                    </Collapse>
                )}
            </Box>
        </motion.div>
    );
}

export function ThinkingPanel({
    isVisible,
    currentStatus,
    toolCalls,
    steps,
}: ThinkingPanelProps) {
    if (!isVisible) return null;

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
                        {steps.map((step, idx) => (
                            <StepCard key={idx} step={step} idx={idx} />
                        ))}

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
