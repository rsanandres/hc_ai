'use client';

import { useState, useCallback, KeyboardEvent } from 'react';
import { Box, TextField, IconButton, alpha, CircularProgress, Tooltip } from '@mui/material';
import { Send, Square } from 'lucide-react'; // Added Square
import { motion } from 'framer-motion';

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void; // Added onStop prop
  isLoading: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, onStop, isLoading, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = useCallback(() => {
    if (input.trim() && !isLoading && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  }, [input, isLoading, disabled, onSend]);

  const handleStop = useCallback(() => {
    if (onStop) {
      onStop();
    }
  }, [onStop]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <Box
      sx={{
        p: 2,
        borderTop: '1px solid',
        borderColor: 'divider',
        bgcolor: (theme) => alpha(theme.palette.background.paper, 0.5),
      }}
    >
      <Box
        sx={{
          display: 'flex',
          gap: 1,
          alignItems: 'flex-end',
        }}
      >
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder="Ask about clinical data..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || (isLoading && !onStop)}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: '12px',
              bgcolor: (theme) => alpha(theme.palette.common.white, 0.03),
              '&:hover': {
                bgcolor: (theme) => alpha(theme.palette.common.white, 0.05),
              },
              '&.Mui-focused': {
                bgcolor: (theme) => alpha(theme.palette.common.white, 0.05),
              },
            },
          }}
        />
        <motion.div
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {isLoading ? (
            <Tooltip title="Stop generation">
              <IconButton
                onClick={handleStop}
                sx={{
                  width: 48,
                  height: 48,
                  bgcolor: 'error.main', // Red color for stop
                  color: 'error.contrastText',
                  borderRadius: '12px',
                  '&:hover': {
                    bgcolor: 'error.dark',
                  },
                }}
              >
                <Square size={20} fill="currentColor" />
              </IconButton>
            </Tooltip>
          ) : (
            <IconButton
              onClick={handleSend}
              disabled={!input.trim() || disabled}
              sx={{
                width: 48,
                height: 48,
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                borderRadius: '12px',
                '&:hover': {
                  bgcolor: 'primary.dark',
                },
                '&.Mui-disabled': {
                  bgcolor: (theme) => alpha(theme.palette.primary.main, 0.3),
                  color: (theme) => alpha(theme.palette.primary.contrastText, 0.5),
                },
              }}
            >
              <Send size={20} />
            </IconButton>
          )}
        </motion.div>
      </Box>
    </Box>
  );
}
