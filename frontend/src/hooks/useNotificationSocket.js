import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/auth.store';

const _apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE  = new URL(_apiUrl).origin.replace(/^http/, 'ws');

/**
 * useNotificationSocket
 *
 * Connects to ws://<host>/ws/notifications/?token=JWT (personal channel).
 * Calls onMessage(payload) whenever the server pushes an event.
 *
 * Usage:
 *   useNotificationSocket((msg) => {
 *     if (msg.type === 'new_message') showToast(msg.from, msg.preview);
 *   });
 */
export function useNotificationSocket(onMessage) {
  const token    = useAuthStore((s) => s.accessToken);
  const wsRef    = useRef(null);
  const cbRef    = useRef(onMessage);

  // keep callback ref up to date without reconnecting
  useEffect(() => { cbRef.current = onMessage; }, [onMessage]);

  useEffect(() => {
    if (!token) return;

    let retryTimer = null;
    let destroyed  = false;

    const connect = () => {
      if (destroyed) return;
      const ws = new WebSocket(`${WS_BASE}/ws/notifications/?token=${token}`);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          cbRef.current?.(data);
        } catch {}
      };

      ws.onclose = () => {
        if (!destroyed) {
          // Reconnect after 3 s
          retryTimer = setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      destroyed = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [token]);
}
