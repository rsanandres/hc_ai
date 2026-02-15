import { useState } from 'react';
import { Box, Typography, Button, Modal, IconButton, alpha, Tooltip } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Linkedin, Mail, Sparkles, ExternalLink, Github, Copy, Check } from 'lucide-react';
import { glassStyle } from '@/theme/theme';
import { MY_EMAIL, MY_LINKEDIN, MY_GITHUB } from '@/data/constants';

interface ConnectModalProps {
  open: boolean;
  onClose: () => void;
}

export function ConnectModal({ open, onClose }: ConnectModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(MY_EMAIL);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal open={open} onClose={onClose}>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '90%',
              maxWidth: 420,
              outline: 'none',
            }}
          >
            <Box
              sx={{
                borderRadius: '20px',
                p: 4,
                ...glassStyle,
                bgcolor: 'background.paper',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {/* Background gradient */}
              <Box
                sx={{
                  position: 'absolute',
                  top: -50,
                  right: -50,
                  width: 200,
                  height: 200,
                  borderRadius: '50%',
                  background: (theme) => `radial-gradient(circle, ${alpha(theme.palette.primary.main, 0.15)} 0%, transparent 70%)`,
                  pointerEvents: 'none',
                }}
              />
              <Box
                sx={{
                  position: 'absolute',
                  bottom: -30,
                  left: -30,
                  width: 150,
                  height: 150,
                  borderRadius: '50%',
                  background: (theme) => `radial-gradient(circle, ${alpha(theme.palette.secondary.main, 0.1)} 0%, transparent 70%)`,
                  pointerEvents: 'none',
                }}
              />

              {/* Close button */}
              <IconButton
                onClick={onClose}
                sx={{
                  position: 'absolute',
                  top: 12,
                  right: 12,
                  color: 'text.secondary',
                }}
              >
                <X size={18} />
              </IconButton>

              {/* Content */}
              <Box sx={{ position: 'relative', zIndex: 1 }}>
                {/* Icon */}
                <Box
                  sx={{
                    width: 56,
                    height: 56,
                    borderRadius: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                    color: 'primary.main',
                    mb: 2.5,
                  }}
                >
                  <Sparkles size={28} />
                </Box>

                {/* Title */}
                <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
                  Enjoying the demo?
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  I&apos;d love to connect! Let&apos;s chat about RAG systems,
                  healthcare AI, or potential opportunities.
                </Typography>

                {/* Contact Links */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

                  {/* Copy Email Button */}
                  <Tooltip title={copied ? "Copied!" : "Click to copy email"} arrow>
                    <Button
                      fullWidth
                      variant="outlined"
                      onClick={handleCopyEmail}
                      startIcon={<Mail size={20} />}
                      endIcon={copied ? <Check size={16} /> : <Copy size={16} />}
                      sx={{
                        borderRadius: '12px',
                        py: 1.5,
                        px: 2,
                        justifyContent: 'flex-start',
                        textTransform: 'none',
                        borderColor: copied ? 'success.main' : 'divider',
                        color: copied ? 'success.main' : 'text.primary',
                        bgcolor: copied ? (theme) => alpha(theme.palette.success.main, 0.05) : 'transparent',
                        '&:hover': {
                          borderColor: copied ? 'success.main' : 'primary.main',
                          bgcolor: (theme) => alpha(copied ? theme.palette.success.main : theme.palette.primary.main, 0.05),
                        },
                        '& .MuiButton-endIcon': {
                          marginLeft: 'auto',
                          opacity: 0.5,
                          color: copied ? 'success.main' : 'inherit',
                        },
                      }}
                    >
                      {MY_EMAIL}
                    </Button>
                  </Tooltip>

                  {/* LinkedIn Link */}
                  <Button
                    component="a"
                    href={MY_LINKEDIN}
                    target="_blank"
                    rel="noopener noreferrer"
                    fullWidth
                    variant="outlined"
                    startIcon={<Linkedin size={20} />}
                    endIcon={<ExternalLink size={16} />}
                    sx={{
                      borderRadius: '12px',
                      py: 1.5,
                      px: 2,
                      justifyContent: 'flex-start',
                      textTransform: 'none',
                      borderColor: 'divider',
                      color: 'text.primary',
                      '&:hover': {
                        borderColor: '#0A66C2',
                        bgcolor: alpha('#0A66C2', 0.05),
                      },
                      '& .MuiButton-endIcon': {
                        marginLeft: 'auto',
                        opacity: 0.5,
                      },
                    }}
                  >
                    Raphael San Andres
                  </Button>

                  {/* GitHub Link */}
                  <Button
                    component="a"
                    href={MY_GITHUB}
                    target="_blank"
                    rel="noopener noreferrer"
                    fullWidth
                    variant="outlined"
                    startIcon={<Github size={20} />}
                    endIcon={<ExternalLink size={16} />}
                    sx={{
                      borderRadius: '12px',
                      py: 1.5,
                      px: 2,
                      justifyContent: 'flex-start',
                      textTransform: 'none',
                      borderColor: 'divider',
                      color: 'text.primary',
                      '&:hover': {
                        borderColor: '#24292e',
                        bgcolor: alpha('#24292e', 0.05),
                      },
                      '& .MuiButton-endIcon': {
                        marginLeft: 'auto',
                        opacity: 0.5,
                      },
                    }}
                  >
                    rsanandres
                  </Button>

                  {/* Close Button */}
                  <Button
                    variant="contained"
                    onClick={onClose}
                    sx={{
                      mt: 1,
                      borderRadius: '12px',
                      py: 1.25,
                      bgcolor: 'primary.main',
                      '&:hover': {
                        bgcolor: 'primary.dark',
                      },
                    }}
                  >
                    Got it, thanks!
                  </Button>
                </Box>
              </Box>
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </Modal>
  );
}
