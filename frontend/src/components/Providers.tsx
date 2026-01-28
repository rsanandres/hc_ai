'use client';

import { ThemeProvider, CssBaseline } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { useState } from 'react';
import { darkTheme } from '@/theme/theme';
import { DebugModeProvider } from '@/hooks/useDebugMode';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
        refetchOnWindowFocus: false,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={darkTheme}>
        <CssBaseline />
        <DebugModeProvider>
          <Toaster
            position="bottom-right"
            theme="dark"
            toastOptions={{
              style: {
                background: '#1a1a24',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#f4f4f5',
              },
            }}
          />
          {children}
        </DebugModeProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

