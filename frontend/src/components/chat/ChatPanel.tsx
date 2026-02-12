'use client';

import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, IconButton, Tooltip, alpha, Switch, FormControlLabel, Chip } from '@mui/material';
import { Trash2, Bug, User, Download, Keyboard } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Message } from '@/types';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { ThinkingPanel } from './ThinkingPanel';
import { KeyboardShortcuts } from './KeyboardShortcuts';
import { glassStyle } from '@/theme/theme';
import { useDebugMode } from '@/hooks/useDebugMode';
import { StreamingState } from '@/hooks/useChat';
import { exportChatAsMarkdown, downloadMarkdown } from '@/utils/exportChat';

// Patient type for selection
interface SelectedPatient {
  id: string;
  name: string;
}

interface ChatPanelProps {
  messages: Message[];
  isLoading: boolean;
  error?: string | null;
  onSend: (message: string) => void;
  onStop?: () => void;
  onClear: () => void;
  onOpenSessions?: () => void;
  streamingState?: StreamingState;
  externalInput?: string;
  selectedPatient?: SelectedPatient | null;
  onFeedback?: (messageId: string, feedback: 'positive' | 'negative') => void;
  onRegenerate?: (messageId: string) => void;
}

export function ChatPanel({
  messages,
  isLoading,
  error,
  onSend,
  onStop,
  onClear,
  onOpenSessions: _onOpenSessions,
  streamingState,
  externalInput,
  selectedPatient,
  onFeedback,
  onRegenerate,
}: ChatPanelProps) {
  const { debugMode, toggleDebugMode } = useDebugMode();
  const isPatientSelected = !!selectedPatient;
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  // Global Cmd+/ shortcut
  const handleKeyDown = useCallback((e: globalThis.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === '/') {
      e.preventDefault();
      setShortcutsOpen(prev => !prev);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleExport = () => {
    const md = exportChatAsMarkdown(messages, selectedPatient?.name);
    downloadMarkdown(md, `atlas-chat-${new Date().toISOString().slice(0, 10)}.md`);
    toast.success('Chat exported');
  };

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
            {selectedPatient ? (
              <Chip
                icon={<User size={12} />}
                label={selectedPatient.name}
                size="small"
                color="primary"
                variant="outlined"
                sx={{ mt: 0.5, height: 22, fontSize: '0.7rem' }}
              />
            ) : (
              <Typography variant="caption" color="text.secondary">
                Select a patient to begin
              </Typography>
            )}
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
            </Tooltip>

            <Tooltip title="Keyboard shortcuts (Cmd+/)">
              <IconButton
                size="small"
                onClick={() => setShortcutsOpen(true)}
                sx={{ color: 'text.secondary' }}
              >
                <Keyboard size={18} />
              </IconButton>
            </Tooltip>

            <Tooltip title="Export chat">
              <IconButton
                size="small"
                onClick={handleExport}
                disabled={messages.length === 0}
                sx={{ color: 'text.secondary' }}
              >
                <Download size={18} />
              </IconButton>
            </Tooltip>

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

        {/* Messages or Patient Selection Prompt */}
        {!isPatientSelected ? (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              p: 4,
              textAlign: 'center',
            }}
          >
            <Box
              sx={{
                width: 64,
                height: 64,
                borderRadius: '50%',
                bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mb: 2,
              }}
            >
              <User size={32} style={{ opacity: 0.6 }} />
            </Box>
            <Typography variant="h6" sx={{ mb: 1, fontWeight: 500 }}>
              Select a Patient
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 300 }}>
              Choose a patient from the Reference panel on the right to start analyzing their clinical data.
            </Typography>
          </Box>
        ) : (
          <MessageList messages={messages} debugMode={debugMode} onFeedback={onFeedback} onRegenerate={onRegenerate} />
        )}

        {/* Thinking Panel (Debug Mode) - persists after completion to show progress */}
        {debugMode && streamingState && (
          <ThinkingPanel
            isVisible={streamingState.isStreaming || isLoading || streamingState.steps.length > 0}
            currentStatus={streamingState.currentStatus}
            toolCalls={streamingState.toolCalls}
            steps={streamingState.steps}
          />
        )}

        {/* Input */}
        <ChatInput
          onSend={onSend}
          onStop={onStop}
          isLoading={isLoading}
          disabled={!!error || !isPatientSelected}
          externalInput={externalInput}
          placeholder={isPatientSelected ? "Ask about clinical data..." : "Select a patient first..."}
        />
      </Box>

      <KeyboardShortcuts open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </motion.div>
  );
}
