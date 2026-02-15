'use client';

import { Box, Typography, alpha, useTheme } from '@mui/material';
import { Github, Linkedin, Mail, FileText } from 'lucide-react';
import { MY_NAME, MY_EMAIL, MY_LINKEDIN, GITHUB_REPO } from '@/data/constants';

const LINKS = [
  { label: 'GitHub', href: GITHUB_REPO, icon: Github, external: true },
  { label: 'LinkedIn', href: MY_LINKEDIN, icon: Linkedin, external: true },
  { label: 'Email', href: `mailto:${MY_EMAIL}`, icon: Mail, external: false },
  { label: 'Docs', href: '/docs', icon: FileText, external: false },
];

export function Footer() {
  const theme = useTheme();

  return (
    <Box
      component="footer"
      sx={{
        borderTop: '1px solid',
        borderColor: 'divider',
        pt: 4,
        pb: 4,
        mt: 6,
        textAlign: 'center',
      }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Built by {MY_NAME}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: { xs: 2, sm: 3 },
        }}
      >
        {LINKS.map((link) => {
          const Icon = link.icon;
          return (
            <Box
              key={link.label}
              component="a"
              href={link.href}
              target={link.external ? '_blank' : undefined}
              rel={link.external ? 'noopener noreferrer' : undefined}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.75,
                color: 'text.disabled',
                textDecoration: 'none',
                fontSize: '0.85rem',
                transition: 'color 0.2s',
                '&:hover': {
                  color: 'primary.main',
                },
              }}
            >
              <Icon size={15} />
              {link.label}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
