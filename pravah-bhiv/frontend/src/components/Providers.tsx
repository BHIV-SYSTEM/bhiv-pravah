'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 4000,
        refetchInterval: 5000,
        retry: 2,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster 
        theme="dark" 
        position="top-right" 
        richColors 
        closeButton 
        toastOptions={{
          style: {
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            backgroundColor: 'var(--card)',
            color: 'var(--foreground)',
            borderColor: 'var(--border)',
          }
        }} 
      />
    </QueryClientProvider>
  );
}
