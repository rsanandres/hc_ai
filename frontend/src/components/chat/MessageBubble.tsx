'use client';

import { Box, Typography, Chip, Stack, Skeleton, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import { User, Bot, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Message } from '@/types';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isLoading = message.isLoading;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Box
        sx={{
          display: 'flex',
          gap: 1.5,
          mb: 2,
          flexDirection: isUser ? 'row-reverse' : 'row',
        }}
      >
        {/* Avatar */}
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            bgcolor: isUser 
              ? (theme) => alpha(theme.palette.primary.main, 0.15)
              : (theme) => alpha(theme.palette.secondary.main, 0.15),
            color: isUser ? 'primary.main' : 'secondary.main',
          }}
        >
          {isUser ? <User size={18} /> : <Bot size={18} />}
        </Box>

        {/* Message content */}
        <Box
          sx={{
            maxWidth: '80%',
            minWidth: isLoading ? '200px' : 'auto',
          }}
        >
          <Box
            sx={{
              px: 2,
              py: 1.5,
              borderRadius: '12px',
              borderTopLeftRadius: isUser ? '12px' : '4px',
              borderTopRightRadius: isUser ? '4px' : '12px',
              bgcolor: isUser 
                ? (theme) => alpha(theme.palette.primary.main, 0.1)
                : (theme) => alpha(theme.palette.background.paper, 0.6),
              border: '1px solid',
              borderColor: isUser 
                ? (theme) => alpha(theme.palette.primary.main, 0.2)
                : 'divider',
            }}
          >
            {isLoading ? (
              <Stack spacing={1}>
                <Skeleton variant="text" width="100%" />
                <Skeleton variant="text" width="80%" />
                <Skeleton variant="text" width="60%" />
              </Stack>
            ) : (
              <Typography
                component="div"
                variant="body1"
                sx={{
                  '& p': { m: 0, mb: 1.5, '&:last-child': { mb: 0 } },
                  '& ul, & ol': { m: 0, pl: 2.5, mb: 1.5 },
                  '& li': { mb: 0.5 },
                  '& code': {
                    bgcolor: (theme) => alpha(theme.palette.common.white, 0.08),
                    px: 0.75,
                    py: 0.25,
                    borderRadius: '4px',
                    fontSize: '0.85em',
                    fontFamily: 'var(--font-geist-mono)',
                  },
                  '& pre': {
                    m: 0,
                    mb: 1.5,
                    borderRadius: '8px',
                    overflow: 'hidden',
                    '& code': {
                      bgcolor: 'transparent',
                      p: 0,
                    },
                  },
                  '& a': {
                    color: 'primary.main',
                    textDecoration: 'none',
                    '&:hover': { textDecoration: 'underline' },
                  },
                  '& strong': { fontWeight: 600 },
                }}
              >
                <ReactMarkdown
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '');
                      const isInline = !match;
                      return isInline ? (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      ) : (
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </Typography>
            )}
          </Box>

          {/* Sources */}
          {message.sources && message.sources.length > 0 && (
            <Stack direction="row" spacing={0.5} sx={{ mt: 1, flexWrap: 'wrap', gap: 0.5 }}>
              {message.sources.slice(0, 3).map((source, idx) => (
                <Chip
                  key={idx}
                  icon={<FileText size={12} />}
                  label={source.doc_id.slice(0, 20) + '...'}
                  size="small"
                  variant="outlined"
                  sx={{
                    height: 24,
                    fontSize: '0.7rem',
                    '& .MuiChip-icon': { ml: 0.5 },
                  }}
                />
              ))}
              {message.sources.length > 3 && (
                <Chip
                  label={`+${message.sources.length - 3} more`}
                  size="small"
                  variant="outlined"
                  sx={{ height: 24, fontSize: '0.7rem' }}
                />
              )}
            </Stack>
          )}

          {/* Timestamp */}
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mt: 0.5,
              color: 'text.disabled',
              textAlign: isUser ? 'right' : 'left',
            }}
          >
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Typography>
        </Box>
      </Box>
    </motion.div>
  );
}
