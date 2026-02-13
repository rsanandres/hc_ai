'use client';

import { useState } from 'react';
import { Box, Typography, Card, CardActionArea, CardContent, Chip, Button, alpha, useMediaQuery, useTheme } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, MessageSquare, User, Database } from 'lucide-react';
import { FEATURED_PATIENTS, RECOMMENDED_PROMPTS, FeaturedPatient } from '@/data/featured-patients';

interface WelcomeScreenProps {
  onStart: (patient: { id: string; name: string }, prompt: string) => void;
}

export function WelcomeScreen({ onStart }: WelcomeScreenProps) {
  const [selectedPatient, setSelectedPatient] = useState<FeaturedPatient | null>(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  const columns = isMobile ? 1 : isTablet ? 2 : 3;

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        position: 'relative',
        overflow: 'auto',
      }}
    >
      {/* Background gradient effects (matches MainLayout) */}
      <Box
        sx={{
          position: 'fixed',
          top: '-20%',
          left: '-10%',
          width: '50%',
          height: '50%',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${alpha(theme.palette.primary.main, 0.08)} 0%, transparent 60%)`,
          pointerEvents: 'none',
          filter: 'blur(60px)',
        }}
      />
      <Box
        sx={{
          position: 'fixed',
          bottom: '-20%',
          right: '-10%',
          width: '60%',
          height: '60%',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${alpha(theme.palette.secondary.main, 0.06)} 0%, transparent 60%)`,
          pointerEvents: 'none',
          filter: 'blur(80px)',
        }}
      />

      {/* Content */}
      <Box
        sx={{
          position: 'relative',
          zIndex: 1,
          maxWidth: 1100,
          mx: 'auto',
          px: { xs: 2, sm: 3, md: 4 },
          py: { xs: 4, sm: 6, md: 8 },
        }}
      >
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Box sx={{ textAlign: 'center', mb: { xs: 4, md: 6 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 2 }}>
              <Activity size={28} color={theme.palette.primary.main} />
              <Typography variant="h3" fontWeight={700} sx={{ letterSpacing: '-0.02em' }}>
                HC AI
              </Typography>
            </Box>
            <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 520, mx: 'auto' }}>
              Explore patient records with AI-powered search across FHIR clinical data.
              Select a patient to get started.
            </Typography>
          </Box>
        </motion.div>

        {/* Step 1: Patient Selection */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <User size={18} color={theme.palette.text.secondary} />
            <Typography variant="subtitle1" fontWeight={600} color="text.secondary">
              Select a Patient
            </Typography>
            <Chip
              label={`${FEATURED_PATIENTS.length} featured`}
              size="small"
              icon={<Database size={12} />}
              sx={{ height: 20, fontSize: '0.65rem' }}
              color="success"
            />
          </Box>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `repeat(${columns}, 1fr)`,
              gap: 1.5,
              mb: 4,
            }}
          >
            {FEATURED_PATIENTS.map((patient, i) => {
              const isSelected = selectedPatient?.id === patient.id;
              return (
                <motion.div
                  key={patient.id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.2 + i * 0.03 }}
                >
                  <Card
                    variant="outlined"
                    sx={{
                      bgcolor: isSelected
                        ? alpha(theme.palette.primary.main, 0.15)
                        : alpha(theme.palette.background.paper, 0.4),
                      backdropFilter: 'blur(10px)',
                      borderColor: isSelected ? 'primary.main' : 'divider',
                      borderWidth: isSelected ? 2 : 1,
                      transition: 'all 0.2s',
                      '&:hover': {
                        bgcolor: isSelected
                          ? alpha(theme.palette.primary.main, 0.2)
                          : alpha(theme.palette.background.paper, 0.6),
                        borderColor: 'primary.main',
                        transform: 'translateY(-2px)',
                      },
                      height: '100%',
                    }}
                  >
                    <CardActionArea
                      onClick={() => setSelectedPatient(isSelected ? null : patient)}
                      sx={{ height: '100%' }}
                    >
                      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                          <Box
                            sx={{
                              width: 36,
                              height: 36,
                              borderRadius: '50%',
                              bgcolor: isSelected ? 'primary.main' : 'action.selected',
                              color: isSelected ? 'primary.contrastText' : 'text.primary',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '0.9rem',
                              flexShrink: 0,
                            }}
                          >
                            {patient.name.charAt(0)}
                          </Box>
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography variant="subtitle2" fontWeight={700} noWrap>
                              {patient.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {patient.age} yrs
                              {patient.chunks ? ` \u00B7 ${patient.chunks} records` : ''}
                            </Typography>
                          </Box>
                          {isSelected && (
                            <Chip label="Selected" size="small" color="primary" sx={{ height: 20, fontSize: '0.6rem' }} />
                          )}
                        </Box>
                        <Typography variant="caption" color="text.secondary" sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                          {patient.conditions.join(' \u00B7 ')}
                        </Typography>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </motion.div>
              );
            })}
          </Box>
        </motion.div>

        {/* Step 2: Starter Questions (appears after patient selected) */}
        <AnimatePresence>
          {selectedPatient && (
            <motion.div
              initial={{ opacity: 0, y: 20, height: 0 }}
              animate={{ opacity: 1, y: 0, height: 'auto' }}
              exit={{ opacity: 0, y: 10, height: 0 }}
              transition={{ duration: 0.35 }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <MessageSquare size={18} color={theme.palette.text.secondary} />
                <Typography variant="subtitle1" fontWeight={600} color="text.secondary">
                  Ask a Question about {selectedPatient.name}
                </Typography>
              </Box>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                  gap: 1.5,
                }}
              >
                {RECOMMENDED_PROMPTS.map((prompt, i) => (
                  <motion.div
                    key={prompt}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25, delay: i * 0.05 }}
                  >
                    <Button
                      fullWidth
                      variant="outlined"
                      onClick={() => onStart({ id: selectedPatient.id, name: selectedPatient.name }, prompt)}
                      sx={{
                        justifyContent: 'flex-start',
                        textAlign: 'left',
                        textTransform: 'none',
                        borderColor: 'divider',
                        color: 'text.primary',
                        py: 1.5,
                        px: 2,
                        '&:hover': {
                          bgcolor: alpha(theme.palette.primary.main, 0.1),
                          borderColor: 'primary.main',
                        },
                      }}
                    >
                      {prompt}
                    </Button>
                  </motion.div>
                ))}
              </Box>
            </motion.div>
          )}
        </AnimatePresence>
      </Box>
    </Box>
  );
}
