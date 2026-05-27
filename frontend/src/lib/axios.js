import axios from 'axios';
import { useAuthStore } from '@/stores/auth.store';
import { tabSync, TAB_EVENTS } from '@/lib/tabSync';

const SHOULD_LOG_API = import.meta.env.DEV || import.meta.env.VITE_DEBUG_API === 'true';

const safePreview = (value) => {
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return value;
  }
};

const logApi = (phase, config, payload) => {
  if (!SHOULD_LOG_API) return;

  const method = (config?.method || 'GET').toUpperCase();
  const url = `${config?.baseURL || ''}${config?.url || ''}`;
  const label = `[API:${phase}] ${method} ${url}`;

  if (phase === 'REQUEST') {
    console.groupCollapsed(label);
    console.log('params:', safePreview(config?.params));
    console.log('data:', safePreview(config?.data));
    console.groupEnd();
    return;
  }

  if (phase === 'RESPONSE') {
    const duration = config?.metadata?.startedAt ? `${Date.now() - config.metadata.startedAt}ms` : 'n/a';
    console.groupCollapsed(`${label} -> ${payload?.status ?? '200'} (${duration})`);
    console.log('response:', safePreview(payload?.data));
    console.groupEnd();
    return;
  }

  if (phase === 'ERROR') {
    const duration = config?.metadata?.startedAt ? `${Date.now() - config.metadata.startedAt}ms` : 'n/a';
    console.groupCollapsed(`${label} -> ERROR${payload?.status ? ` ${payload.status}` : ''} (${duration})`);
    console.log('error:', safePreview(payload?.data || payload?.message || payload));
    console.groupEnd();
  }
};

/**
 * Axios instance configuration
 * Includes interceptors for auth, error handling, and request/response transformation
 */
const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor
 * Adds auth token to requests
 */
axiosInstance.interceptors.request.use(
  (config) => {
    config.metadata = { startedAt: Date.now() };

    // Normalise config.url to strip duplicate '/api/v1' if baseURL already ends with it
    if (config.url && (config.url.startsWith('/api/v1/') || config.url === '/api/v1')) {
      const apiPrefix = '/api/v1';
      const baseURLHasPrefix = config.baseURL && (config.baseURL.endsWith(apiPrefix) || config.baseURL.endsWith(apiPrefix + '/'));
      if (baseURLHasPrefix) {
        config.url = config.url === '/api/v1' ? '/' : config.url.substring(apiPrefix.length);
      }
    }

    const token = useAuthStore.getState().accessToken;
    const isAuthEndpointRequest =
      config.url?.includes('/auth/login/') ||
      config.url?.includes('/auth/register/') ||
      config.url?.includes('/auth/refresh/') ||
      config.url?.includes('/auth/google/') ||
      config.url?.includes('/auth/mfa/') ||
      config.url?.includes('/auth/otp/');
    if (token && !isAuthEndpointRequest) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    logApi('REQUEST', config);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor
 * Handles errors and token refresh
 */
axiosInstance.interceptors.response.use(
  (response) => {
    logApi('RESPONSE', response.config, response);
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;
    const requestUrl = originalRequest?.url || '';

    logApi('ERROR', originalRequest, error.response || error);

    const isAuthEndpoint =
      requestUrl.includes('/auth/login/') ||
      requestUrl.includes('/auth/register/') ||
      requestUrl.includes('/auth/google/') ||
      requestUrl.includes('/auth/mfa/') ||
      requestUrl.includes('/auth/otp/') ||
      requestUrl.includes('/auth/refresh/');

    if (status === 401 && !originalRequest?._retry && !isAuthEndpoint) {
      const { refreshToken, clearSession, setAccessToken } = useAuthStore.getState();

      if (refreshToken) {
        originalRequest._retry = true;

        try {
          const refreshResponse = await axiosInstance.post('/api/v1/auth/refresh/', {
            refresh: refreshToken,
          }, {
            _retry: true,
          });

          const accessToken = refreshResponse?.data?.data?.access;
          if (accessToken) {
            setAccessToken(accessToken);
            tabSync.emit(TAB_EVENTS.TOKEN_REFRESHED, { accessToken });

            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `Bearer ${accessToken}`;
            return axiosInstance(originalRequest);
          }
        } catch (refreshError) {
          clearSession();
          // Don't emit LOGOUT here — it would hard-redirect the current tab.
          // ProtectedRoute will redirect to /login once accessToken is null.
          return Promise.reject(refreshError);
        }
      }

      clearSession();
      // Don't emit LOGOUT — let ProtectedRoute handle the redirect smoothly.
    }

    return Promise.reject(error);
  }
);

export { axiosInstance };
