import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { queryClient } from '@/lib/queryClient';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      // Persisted: user info and refresh token survive page reloads
      user: null,
      refreshToken: null,

      // Not persisted: access token is in-memory only for security
      accessToken: null,
      isInitialized: false,

      setSession: ({ accessToken, refreshToken, user }) => {
        set({ accessToken, refreshToken, user, isInitialized: true });
      },

      setInitialized: (isInitialized = true) => set({ isInitialized }),

      setAccessToken: (accessToken) => set({ accessToken }),

      setUser: (user) => set({ user }),

      clearSession: () => {
        // Keep isInitialized:true so ProtectedRoute immediately redirects to /login
        // instead of showing a loading spinner before redirecting
        set({ accessToken: null, refreshToken: null, user: null, isInitialized: true });
        // Wipe cached React Query data (risk scores, insights, etc.) so the
        // next login — possibly a different patient in the same tab — never
        // sees a stale, cross-account cached result before its own fetch lands.
        queryClient.clear();
      },

      isAuthenticated: () => {
        const { accessToken } = get();
        return !!accessToken;
      },

      hasRole: (role) => {
        const { user } = get();
        if (!user) return false;
        
        if (role === 'ADMIN' && user.role === 'SUPER_ADMIN') {
          return true;
        }
        
        if (Array.isArray(role)) {
          return role.includes(user.role);
        }
        
        return user.role === role;
      },
    }),
    {
      name: 'medadhere_auth',
      storage: {
        getItem: (name) => {
          const item = localStorage.getItem(name);
          return item ? JSON.parse(item) : null;
        },
        setItem: (name, value) => {
          localStorage.setItem(name, JSON.stringify(value));
        },
        removeItem: (name) => {
          localStorage.removeItem(name);
        },
      },
      // Only persist user and refreshToken (never persist accessToken)
      partialize: (state) => ({
        user: state.user,
        refreshToken: state.refreshToken,
      }),
    }
  )
);
