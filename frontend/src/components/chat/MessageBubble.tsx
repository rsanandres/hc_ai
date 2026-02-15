'use client';

import { useState, useCallback } from 'react';
import { Box, Typography, Chip, Stack, Skeleton, alpha, IconButton, Tooltip } from '@mui/material';
import { motion } from 'framer-motion';
import { User, Bot, FileText, ThumbsUp, ThumbsDown, RefreshCw, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { toast } from 'sonner';
import { Message } from '@/types';

interface MessageBubbleProps {
  message: Message;
  onFeedback?: (messageId: string, feedback: 'positive' | 'negative') => void;
  onRegenerate?: (messageId: string) => void;
}

export function MessageBubble({ message, onFeedback, onRegenerate }: MessageBubbleProps) {
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
                      if (isInline) {
                        return (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        );
                      }
                      const codeString = String(children).replace(/\n$/, '');
                      return (
                        <CodeBlock language={match[1]} code={codeString} />
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

          {/* Timestamp + Feedback + Regenerate */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
            <Typography
              variant="caption"
              sx={{
                color: 'text.disabled',
                flex: 1,
                textAlign: isUser ? 'right' : 'left',
              }}
            >
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </Typography>

            {/* Feedback & Regenerate - assistant messages only, not loading */}
            {!isUser && !isLoading && (
              <Box sx={{ display: 'flex', gap: 0.25 }}>
                <Tooltip title="Good response">
                  <IconButton
                    size="small"
                    onClick={() => onFeedback?.(message.id, 'positive')}
                    sx={{
                      p: 0.5,
                      color: message.feedback === 'positive' ? 'success.main' : 'text.disabled',
                      '&:hover': { color: 'success.main' },
                    }}
                  >
                    <ThumbsUp size={14} fill={message.feedback === 'positive' ? 'currentColor' : 'none'} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Bad response">
                  <IconButton
                    size="small"
                    onClick={() => onFeedback?.(message.id, 'negative')}
                    sx={{
                      p: 0.5,
                      color: message.feedback === 'negative' ? 'error.main' : 'text.disabled',
                      '&:hover': { color: 'error.main' },
                    }}
                  >
                    <ThumbsDown size={14} fill={message.feedback === 'negative' ? 'currentColor' : 'none'} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Regenerate response">
                  <IconButton
                    size="small"
                    onClick={() => onRegenerate?.(message.id)}
                    sx={{
                      p: 0.5,
                      color: 'text.disabled',
                      '&:hover': { color: 'text.primary' },
                    }}
                  >
                    <RefreshCw size={14} />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
          </Box>
        </Box>
      </Box>
    </motion.div>
  );
}

/** Code block with copy button */
function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <Box sx={{ position: 'relative', '&:hover .copy-btn': { opacity: 1 } }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: '#282c34',
          px: 1.5,
          pt: 0.5,
          borderTopLeftRadius: '8px',
          borderTopRightRadius: '8px',
        }}
      >
        <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.7rem' }}>
          {language}
        </Typography>
        <IconButton
          className="copy-btn"
          size="small"
          onClick={handleCopy}
          sx={{
            opacity: 0,
            transition: 'opacity 0.2s',
            color: 'text.disabled',
            p: 0.5,
            '&:hover': { color: 'text.primary' },
          }}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </IconButton>
      </Box>
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
        customStyle={{ marginTop: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
      >
        {code}
      </SyntaxHighlighter>
    </Box>
  );
}
