'use client';

import { ThemeProvider, CssBaseline } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { useState, useEffect } from 'react';
import { darkTheme } from '@/theme/theme';
import { DebugModeProvider } from '@/hooks/useDebugMode';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [mounted, setMounted] = useState(false);
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: false,
      },
    },
  }));

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Hydration pattern: must detect client mount to avoid SSR mismatch
    setMounted(true);
  }, []);

  return (
    <AppRouterCacheProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={darkTheme}>
          <CssBaseline />
          <DebugModeProvider>
            <ErrorBoundary>
              {mounted && (
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
              )}
              {children}
            </ErrorBoundary>
          </DebugModeProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </AppRouterCacheProvider>
  );
}
