'use client';

import { useState, useRef, useEffect } from 'react';
import { Box, Typography, Card, CardActionArea, CardContent, Chip, Button, alpha, useMediaQuery, useTheme } from '@mui/material';
// motion/AnimatePresence removed — React 19 strict mode breaks framer-motion initial animations
import { Activity, MessageSquare, User, Database, Github, FileText, ChevronDown, ChevronRight, Workflow, FileCheck, Network } from 'lucide-react';
import Image from 'next/image';
import { FEATURED_PATIENTS, RECOMMENDED_PROMPTS, FeaturedPatient } from '@/data/featured-patients';
import { MY_NAME, MY_LINKEDIN, GITHUB_REPO } from '@/data/constants';
import { Footer } from './Footer';

interface WelcomeScreenProps {
  onStart: (patient: { id: string; name: string }, prompt: string) => void;
}

const STATS = [
  { label: '91K patients', key: 'patients' },
  { label: '7.7M vectors', key: 'vectors' },
  { label: '20+ medical tools', key: 'tools' },
  { label: '~$120/mo on AWS', key: 'cost' },
];

const TECH_STACK = ['Python', 'LangGraph', 'pgvector', 'AWS ECS', 'Claude 3.5', 'Next.js', 'Go'];

const HOW_IT_WORKS = [
  {
    step: 1,
    icon: MessageSquare,
    title: 'Ask a Question',
    description: 'Natural language query about any patient\'s clinical records',
  },
  {
    step: 2,
    icon: Workflow,
    title: 'Multi-Agent RAG',
    description: 'Hybrid vector search, cross-encoder reranking, and LLM reasoning with 20+ medical tools',
  },
  {
    step: 3,
    icon: FileCheck,
    title: 'Cited Response',
    description: 'Grounded answers with source chunks, SNOMED codes, and tool citations',
  },
];

export function WelcomeScreen({ onStart }: WelcomeScreenProps) {
  const [selectedPatient, setSelectedPatient] = useState<FeaturedPatient | null>(null);
  const questionsRef = useRef<HTMLDivElement>(null);
  const patientGridRef = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  // Auto-scroll to questions when patient is selected
  useEffect(() => {
    if (selectedPatient && questionsRef.current) {
      setTimeout(() => {
        questionsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 400); // Wait for AnimatePresence animation
    }
  }, [selectedPatient]);

  const columns = isMobile ? 1 : isTablet ? 2 : 3;

  const scrollToPatients = () => {
    patientGridRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

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
        {/* Header / Hero */}
        <Box sx={{ textAlign: 'center', mb: { xs: 4, md: 6 } }}>
          {/* Title */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 1 }}>
            <Activity size={28} color={theme.palette.primary.main} />
            <Typography variant="h3" fontWeight={700} sx={{ letterSpacing: '-0.02em' }}>
              Atlas
            </Typography>
          </Box>

          {/* Byline */}
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            Built by{' '}
            <a
              href={MY_LINKEDIN}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: theme.palette.primary.main, textDecoration: 'none' }}
            >
              {MY_NAME}
            </a>
          </Typography>

          {/* Description */}
          <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 600, mx: 'auto', mb: 2.5 }}>
            An AI agent for exploring and analyzing FHIR clinical data.
            Ask questions in natural language and watch the RAG pipeline retrieve, reason, and respond.
          </Typography>

          {/* Stats row */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 1, mb: 2 }}>
            {STATS.map((stat) => (
              <Chip
                key={stat.key}
                label={stat.label}
                variant="outlined"
                size="small"
                sx={{
                  borderColor: alpha(theme.palette.text.secondary, 0.2),
                  color: 'text.secondary',
                  fontSize: '0.75rem',
                }}
              />
            ))}
          </Box>

          {/* Tech stack pills */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 0.75, mb: 3 }}>
            {TECH_STACK.map((tech) => (
              <Chip
                key={tech}
                label={tech}
                size="small"
                sx={{
                  height: 22,
                  fontSize: '0.65rem',
                  bgcolor: alpha(theme.palette.primary.main, 0.08),
                  color: 'text.secondary',
                  border: 'none',
                }}
              />
            ))}
          </Box>

          {/* CTA buttons */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', sm: 'row' },
              justifyContent: 'center',
              alignItems: 'center',
              gap: 1.5,
              mb: 2.5,
            }}
          >
            <Button
              variant="contained"
              onClick={scrollToPatients}
              endIcon={<ChevronDown size={16} />}
              sx={{ textTransform: 'none', minWidth: 160 }}
            >
              Try the Demo
            </Button>
            <Button
              component="a"
              href={GITHUB_REPO}
              target="_blank"
              rel="noopener noreferrer"
              variant="outlined"
              startIcon={<Github size={16} />}
              sx={{ textTransform: 'none', minWidth: 140 }}
            >
              GitHub
            </Button>
            <Button
              component="a"
              href="/docs"
              variant="outlined"
              startIcon={<FileText size={16} />}
              sx={{ textTransform: 'none', minWidth: 140 }}
            >
              Technical Docs
            </Button>
          </Box>

          {/* Synthea attribution */}
          <Typography variant="caption" color="text.disabled" sx={{ maxWidth: 600, mx: 'auto', display: 'block' }}>
            All patient data is synthetic, generated by{' '}
            <a href="https://synthetichealth.github.io/synthea/" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>
              Synthea
            </a>
            . No real patient information is used.
          </Typography>
        </Box>

        {/* How It Works */}
        <Box sx={{ mb: { xs: 4, md: 6 } }}>
          <Typography variant="h6" fontWeight={700} sx={{ textAlign: 'center', mb: 3 }}>
            How It Works
          </Typography>
          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', md: 'row' },
              alignItems: { xs: 'stretch', md: 'flex-start' },
              justifyContent: 'center',
              gap: { xs: 1, md: 0 },
            }}
          >
            {HOW_IT_WORKS.map((item, index) => {
              const Icon = item.icon;
              return (
                <Box
                  key={item.step}
                  sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', md: 'row' },
                    alignItems: 'center',
                    flex: 1,
                  }}
                >
                  {/* Step card */}
                  <Card
                    variant="outlined"
                    sx={{
                      bgcolor: alpha(theme.palette.background.paper, 0.4),
                      backdropFilter: 'blur(10px)',
                      borderColor: 'divider',
                      flex: 1,
                      width: '100%',
                    }}
                  >
                    <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 }, textAlign: 'center' }}>
                      {/* Step number + icon */}
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 1.5 }}>
                        <Box
                          sx={{
                            width: 24,
                            height: 24,
                            borderRadius: '50%',
                            bgcolor: alpha(theme.palette.primary.main, 0.15),
                            color: 'primary.main',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                          }}
                        >
                          {item.step}
                        </Box>
                        <Box
                          sx={{
                            width: 36,
                            height: 36,
                            borderRadius: '10px',
                            bgcolor: alpha(theme.palette.primary.main, 0.1),
                            color: 'primary.main',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <Icon size={18} />
                        </Box>
                      </Box>
                      <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
                        {item.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.5 }}>
                        {item.description}
                      </Typography>
                    </CardContent>
                  </Card>

                  {/* Arrow between steps */}
                  {index < HOW_IT_WORKS.length - 1 && (
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        px: { xs: 0, md: 1 },
                        py: { xs: 0.5, md: 0 },
                        color: 'text.disabled',
                      }}
                    >
                      <Box sx={{ display: { xs: 'none', md: 'flex' } }}>
                        <ChevronRight size={20} />
                      </Box>
                      <Box sx={{ display: { xs: 'flex', md: 'none' } }}>
                        <ChevronDown size={20} />
                      </Box>
                    </Box>
                  )}
                </Box>
              );
            })}
          </Box>
        </Box>

        {/* Architecture Preview */}
        <Box sx={{ mb: { xs: 4, md: 6 } }}>
          <Card
            component="a"
            href="/docs"
            variant="outlined"
            sx={{
              bgcolor: alpha(theme.palette.background.paper, 0.4),
              backdropFilter: 'blur(10px)',
              borderColor: 'divider',
              textDecoration: 'none',
              display: 'block',
              transition: 'all 0.2s',
              '&:hover': {
                bgcolor: alpha(theme.palette.background.paper, 0.6),
                borderColor: 'primary.main',
              },
            }}
          >
            <CardContent
              sx={{
                p: { xs: 2, md: 3 },
                '&:last-child': { pb: { xs: 2, md: 3 } },
                display: 'flex',
                flexDirection: { xs: 'column', md: 'row' },
                alignItems: 'center',
                gap: { xs: 2, md: 3 },
              }}
            >
              {/* Thumbnail */}
              <Box
                sx={{
                  position: 'relative',
                  width: { xs: '100%', md: 400 },
                  height: { xs: 240, md: 280 },
                  borderRadius: '8px',
                  overflow: 'hidden',
                  border: '1px solid',
                  borderColor: 'divider',
                  flexShrink: 0,
                }}
              >
                <Image
                  src="/aws_architecture.png"
                  alt="AWS architecture diagram"
                  fill
                  style={{ objectFit: 'cover', objectPosition: 'center 90%' }}
                  sizes="(max-width: 900px) 100vw, 340px"
                />
              </Box>

              {/* Text */}
              <Box sx={{ flex: 1, textAlign: { xs: 'center', md: 'left' } }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, justifyContent: { xs: 'center', md: 'flex-start' } }}>
                  <Network size={18} color={theme.palette.primary.main} />
                  <Typography variant="subtitle1" fontWeight={700} color="text.primary">
                    System Architecture
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  Multi-agent LangGraph pipeline on AWS ECS, RDS pgvector, and Bedrock Claude.
                  Includes data flow, database schema, and retrieval pipeline diagrams.
                </Typography>
                <Typography variant="caption" color="primary.main" fontWeight={600}>
                  Read the technical docs &rarr;
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Patient Selection */}
        <Box ref={patientGridRef}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <User size={18} color={theme.palette.text.secondary} />
            <Typography variant="subtitle1" fontWeight={600} color="text.secondary">
              {selectedPatient ? `Patient: ${selectedPatient.name}` : 'Select a Patient'}
            </Typography>
            {!selectedPatient && (
              <Chip
                label={`${FEATURED_PATIENTS.length} featured`}
                size="small"
                icon={<Database size={12} />}
                sx={{ height: 20, fontSize: '0.65rem' }}
                color="success"
              />
            )}
            {selectedPatient && (
              <Chip
                label="Change"
                size="small"
                onClick={() => setSelectedPatient(null)}
                sx={{ height: 20, fontSize: '0.65rem', cursor: 'pointer' }}
                variant="outlined"
              />
            )}
          </Box>

          {!selectedPatient && (
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: `repeat(${columns}, 1fr)`,
                gap: 1.5,
                mb: 4,
              }}
            >
              {FEATURED_PATIENTS.map((patient) => (
                <Card
                  key={patient.id}
                  variant="outlined"
                  sx={{
                    bgcolor: alpha(theme.palette.background.paper, 0.4),
                    backdropFilter: 'blur(10px)',
                    borderColor: 'divider',
                    borderWidth: 1,
                    transition: 'all 0.2s',
                    '&:hover': {
                      bgcolor: alpha(theme.palette.background.paper, 0.6),
                      borderColor: 'primary.main',
                      transform: 'translateY(-2px)',
                    },
                    height: '100%',
                  }}
                >
                  <CardActionArea
                    onClick={() => setSelectedPatient(patient)}
                    sx={{ height: '100%' }}
                  >
                    <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                        <Box
                          sx={{
                            width: 36,
                            height: 36,
                            borderRadius: '50%',
                            bgcolor: 'action.selected',
                            color: 'text.primary',
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
                      </Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {patient.conditions.join(' \u00B7 ')}
                      </Typography>
                    </CardContent>
                  </CardActionArea>
                </Card>
              ))}
            </Box>
          )}
        </Box>

        {/* Starter Questions (appears after patient selected) */}
        {selectedPatient && (
          <Box ref={questionsRef}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <MessageSquare size={18} color={theme.palette.text.secondary} />
              <Typography variant="subtitle1" fontWeight={600} color="text.secondary">
                Ask a Recommended Question about {selectedPatient.name}
              </Typography>
            </Box>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                gap: 1.5,
              }}
            >
              {RECOMMENDED_PROMPTS.map((prompt) => (
                <Button
                  key={prompt}
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
              ))}
            </Box>
          </Box>
        )}

        {/* Footer */}
        <Footer />
      </Box>
    </Box>
  );
}
