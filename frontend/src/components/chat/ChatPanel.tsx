'use client';

import { Box, Typography, IconButton, Tooltip, alpha, Switch, FormControlLabel } from '@mui/material';
import { Trash2, Menu, Bug } from 'lucide-react';
import { motion } from 'framer-motion';
import { Message } from '@/types';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { ThinkingPanel } from './ThinkingPanel';
import { glassStyle } from '@/theme/theme';
import { useDebugMode } from '@/hooks/useDebugMode';
import { StreamingState } from '@/hooks/useChat';

interface ChatPanelProps {
  messages: Message[];
  isLoading: boolean;
  error?: string | null;
  onSend: (message: string) => void;
  onStop?: () => void;
  onClear: () => void;
  onOpenSessions?: () => void;
  streamingState?: StreamingState;
}

export function ChatPanel({
  messages,
  isLoading,
  error,
  onSend,
  onStop,
  onClear,
  onOpenSessions,
  streamingState,
}: ChatPanelProps) {
  const { debugMode, toggleDebugMode } = useDebugMode();

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      style={{ height: '100%' }}
    >
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          borderRadius: '16px',
          overflow: 'hidden',
          ...glassStyle,
        }}
      >
        {/* Header */}
        <Box
          sx={{
            px: 2.5,
            py: 2,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Atlas Chat
            </Typography>
            <Typography variant="caption" color="text.secondary">
              RAG-powered clinical assistant
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
            {/* Debug Mode Toggle */}
            <Tooltip title={debugMode ? "Debug mode ON - showing agent thinking" : "Debug mode OFF"} arrow>
              <FormControlLabel
                control={
                  <Switch
                    size="small"
                    checked={debugMode}
                    onChange={toggleDebugMode}
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': {
                        color: '#ff9800',
                      },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                        backgroundColor: '#ff9800',
                      },
                    }}
                  />
                }
                label={
                  <Bug
                    size={16}
                    style={{
                      color: debugMode ? '#ff9800' : 'rgba(255,255,255,0.5)',
                      marginRight: 4,
                    }}
                  />
                }
                labelPlacement="start"
                sx={{
                  mr: 0.5,
                  '& .MuiFormControlLabel-label': {
                    display: 'flex',
                    alignItems: 'center',
                  },
                }}
              />
            </Tooltip>            {/* Debug Mode Toggle */}

            <Tooltip title="Clear chat">
              <IconButton
                size="small"
                onClick={onClear}
                disabled={messages.length === 0}
                sx={{
                  color: 'text.secondary',
                  '&:hover': { color: 'error.main' },
                }}
              >
                <Trash2 size={18} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Messages */}
        <MessageList messages={messages} debugMode={debugMode} />

        {/* Thinking Panel (Debug Mode) */}
        {debugMode && streamingState && (
          <ThinkingPanel
            isVisible={streamingState.isStreaming || isLoading}
            currentStatus={streamingState.currentStatus}
            toolCalls={streamingState.toolCalls}
            researcherOutput={streamingState.researcherOutput}
            validatorOutput={streamingState.validatorOutput}
            validationResult={streamingState.validationResult}
          />
        )}

        {/* Input */}
        <ChatInput onSend={onSend} onStop={onStop} isLoading={isLoading} disabled={!!error} />
      </Box>
    </motion.div>
  );
}
