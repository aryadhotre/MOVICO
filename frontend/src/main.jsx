import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App.jsx';
import { AuthProvider } from './lib/auth.jsx';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Catalogue data barely changes, and refetching because a user tabbed away
      // and back is the single biggest source of pointless requests.
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Client errors will not fix themselves on a retry.
        if (error?.status >= 400 && error?.status < 500) return false;
        return failureCount < 2;
      },
      staleTime: 60 * 1000,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
