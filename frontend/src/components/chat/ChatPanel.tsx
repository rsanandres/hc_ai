'use client';

import { Box, Typography, IconButton, Tooltip, alpha } from '@mui/material';
import { Trash2, Settings } from 'lucide-react';
import { motion } from 'framer-motion';
import { Message } from '@/types';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { glassStyle } from '@/theme/theme';

interface ChatPanelProps {
  messages: Message[];
  isLoading: boolean;
  onSend: (message: string) => void;
  onClear: () => void;
}

export function ChatPanel({ messages, isLoading, onSend, onClear }: ChatPanelProps) {
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
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Settings">
              <IconButton 
                size="small"
                sx={{ 
                  color: 'text.secondary',
                  '&:hover': { color: 'text.primary' },
                }}
              >
                <Settings size={18} />
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

        {/* Messages */}
        <MessageList messages={messages} />

        {/* Input */}
        <ChatInput onSend={onSend} isLoading={isLoading} />
      </Box>
    </motion.div>
  );
}
