'use client';

import { useEffect, useRef } from 'react';
import { Box, Typography, alpha } from '@mui/material';
import { MessageSquare } from 'lucide-react';
import { Message } from '@/types';
import { MessageBubble } from './MessageBubble';

interface MessageListProps {
  messages: Message[];
  onFeedback?: (messageId: string, feedback: 'positive' | 'negative') => void;
  onRegenerate?: (messageId: string) => void;
}

export function MessageList({ messages, onFeedback, onRegenerate }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
          p: 4,
        }}
      >
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
            color: 'primary.main',
          }}
        >
          <MessageSquare size={28} />
        </Box>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Atlas RAG Agent
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', maxWidth: 400 }}>
          Ask questions about clinical data powered by retrieval-augmented generation.
          Your queries are processed through PII masking, vector search, and Claude 3.5 Sonnet.
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.disabled">
            Try: &quot;What medications is patient 12345 currently taking?&quot;
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        flex: 1,
        overflowY: 'auto',
        p: 2,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          onFeedback={onFeedback}
          onRegenerate={onRegenerate}
        />
      ))}
      <div ref={bottomRef} />
    </Box>
  );
}
