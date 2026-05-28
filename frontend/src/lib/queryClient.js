import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Tab hidden hone par (background) API calling bilkul band ho jayegi
      refetchIntervalInBackground: false,
      // Jaise hi user wapas website par aayega, automatically fresh data aayega
      refetchOnWindowFocus: true,
      retry: 1,
      staleTime: 30_000,
    },
    mutations: {
      retry: 0,
    },
  },
});
