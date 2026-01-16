'use client';

import { createTheme, alpha } from '@mui/material/styles';

// Custom color palette - modern dark theme with teal accent
const palette = {
  primary: {
    main: '#14b8a6',      // Teal
    light: '#5eead4',
    dark: '#0d9488',
    contrastText: '#000000',
  },
  secondary: {
    main: '#8b5cf6',      // Purple accent
    light: '#a78bfa',
    dark: '#7c3aed',
    contrastText: '#ffffff',
  },
  background: {
    default: '#0a0a0f',   // Deep dark
    paper: '#12121a',     // Slightly lighter
  },
  surface: {
    main: '#1a1a24',
    light: '#22222e',
  },
  text: {
    primary: '#f4f4f5',
    secondary: '#a1a1aa',
    disabled: '#52525b',
  },
  success: {
    main: '#22c55e',
    light: '#4ade80',
  },
  warning: {
    main: '#f59e0b',
    light: '#fbbf24',
  },
  error: {
    main: '#ef4444',
    light: '#f87171',
  },
  divider: alpha('#ffffff', 0.08),
};

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    ...palette,
  },
  typography: {
    fontFamily: 'var(--font-geist-sans), system-ui, sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.5rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.25rem',
      fontWeight: 600,
    },
    h5: {
      fontSize: '1rem',
      fontWeight: 600,
    },
    h6: {
      fontSize: '0.875rem',
      fontWeight: 600,
    },
    body1: {
      fontSize: '0.9375rem',
      lineHeight: 1.6,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    caption: {
      fontSize: '0.75rem',
      color: palette.text.secondary,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarWidth: 'thin',
          '&::-webkit-scrollbar': {
            width: '8px',
            height: '8px',
          },
          '&::-webkit-scrollbar-track': {
            background: 'transparent',
          },
          '&::-webkit-scrollbar-thumb': {
            background: alpha('#ffffff', 0.2),
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb:hover': {
            background: alpha('#ffffff', 0.3),
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: palette.background.paper,
          border: `1px solid ${palette.divider}`,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 8,
          padding: '8px 16px',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
            backgroundColor: alpha('#ffffff', 0.02),
            '&:hover': {
              backgroundColor: alpha('#ffffff', 0.04),
            },
            '&.Mui-focused': {
              backgroundColor: alpha('#ffffff', 0.04),
            },
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: palette.surface?.main,
          border: `1px solid ${palette.divider}`,
          borderRadius: 8,
          fontSize: '0.8125rem',
        },
      },
    },
  },
});

// Glass morphism style helper
export const glassStyle = {
  backgroundColor: alpha('#12121a', 0.8),
  backdropFilter: 'blur(12px)',
  border: `1px solid ${alpha('#ffffff', 0.08)}`,
};
