'use client';

import { useState } from 'react';
import { Box, Typography, TextField, Button, Modal, IconButton, alpha } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Linkedin, Mail, Sparkles } from 'lucide-react';
import { glassStyle } from '@/theme/theme';

interface ConnectModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: { email: string; linkedin: string }) => void;
}

export function ConnectModal({ open, onClose, onSubmit }: ConnectModalProps) {
  const [email, setEmail] = useState('');
  const [linkedin, setLinkedin] = useState('');
  const [errors, setErrors] = useState<{ email?: string; linkedin?: string }>({});

  const validate = () => {
    const newErrors: { email?: string; linkedin?: string } = {};
    
    if (!email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Invalid email format';
    }

    if (linkedin.trim() && !linkedin.includes('linkedin.com')) {
      newErrors.linkedin = 'Please enter a valid LinkedIn URL';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (validate()) {
      onSubmit({ email: email.trim(), linkedin: linkedin.trim() });
      setEmail('');
      setLinkedin('');
    }
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
                  I&apos;d love to connect! Drop your info and let&apos;s chat about RAG systems, 
                  healthcare AI, or potential opportunities.
                </Typography>

                {/* Form */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="Email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    error={!!errors.email}
                    helperText={errors.email}
                    InputProps={{
                      startAdornment: <Mail size={18} style={{ marginRight: 8, opacity: 0.5 }} />,
                    }}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        borderRadius: '10px',
                      },
                    }}
                  />

                  <TextField
                    fullWidth
                    label="LinkedIn (optional)"
                    placeholder="linkedin.com/in/yourprofile"
                    value={linkedin}
                    onChange={(e) => setLinkedin(e.target.value)}
                    error={!!errors.linkedin}
                    helperText={errors.linkedin}
                    InputProps={{
                      startAdornment: <Linkedin size={18} style={{ marginRight: 8, opacity: 0.5 }} />,
                    }}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        borderRadius: '10px',
                      },
                    }}
                  />

                  <Box sx={{ display: 'flex', gap: 1.5, mt: 1 }}>
                    <Button
                      variant="outlined"
                      onClick={onClose}
                      sx={{
                        flex: 1,
                        borderRadius: '10px',
                        py: 1.25,
                        borderColor: 'divider',
                        color: 'text.secondary',
                        '&:hover': {
                          borderColor: 'text.secondary',
                          bgcolor: 'transparent',
                        },
                      }}
                    >
                      Maybe later
                    </Button>
                    <Button
                      variant="contained"
                      onClick={handleSubmit}
                      sx={{
                        flex: 1,
                        borderRadius: '10px',
                        py: 1.25,
                        bgcolor: 'primary.main',
                        '&:hover': {
                          bgcolor: 'primary.dark',
                        },
                      }}
                    >
                      Connect
                    </Button>
                  </Box>
                </Box>
              </Box>
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </Modal>
  );
}
