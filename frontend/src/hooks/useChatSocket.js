import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/auth.store';

// Extract only origin (strips /api/v1 or any path suffix from VITE_API_URL)
const _apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE = new URL(_apiUrl).origin.replace(/^http/, 'ws');

/**
 * useChatSocket(roomId)
 * Connects to ws://<host>/ws/chat/<roomId>/?token=<jwt>
 * Returns: { messages, sendMessage, sendTyping, isConnected, isTyping }
 */
export function useChatSocket(roomId) {
  const token = useAuthStore((s) => s.accessToken);
  const user  = useAuthStore((s) => s.user);

  const [messages,    setMessages]    = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTyping,    setIsTyping]    = useState(false); // other party typing

  const wsRef          = useRef(null);
  const typingTimerRef = useRef(null);

  useEffect(() => {
    if (!roomId || !token) return;

    const url = `${WS_BASE}/ws/chat/${roomId}/?token=${token}`;
    const ws  = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        if (data.type === 'history') {
          setMessages(data.messages || []);
          return;
        }
        if (data.type === 'message' || data.type === 'file') {
          setMessages((prev) => [...prev, data]);
          return;
        }
        if (data.type === 'typing') {
          setIsTyping(data.is_typing);
          if (data.is_typing) {
            clearTimeout(typingTimerRef.current);
            typingTimerRef.current = setTimeout(() => setIsTyping(false), 3000);
          }
          return;
        }
        if (data.type === 'read_receipt') {
          setMessages((prev) =>
            prev.map((m) => (m.is_own ? m : { ...m, is_read: true }))
          );
        }
      } catch {}
    };

    ws.onclose  = () => setIsConnected(false);
    ws.onerror  = () => setIsConnected(false);

    return () => {
      ws.close();
      clearTimeout(typingTimerRef.current);
    };
  }, [roomId, token]);

  const sendMessage = useCallback((content) => {
    if (wsRef.current?.readyState === WebSocket.OPEN)
      wsRef.current.send(JSON.stringify({ type: 'message', content }));
  }, []);

  const sendFileMessage = useCallback((fileInfo) => {
    if (wsRef.current?.readyState === WebSocket.OPEN)
      wsRef.current.send(JSON.stringify({ type: 'file', ...fileInfo }));
  }, []);

  const sendTyping = useCallback((isTypingNow) => {
    if (wsRef.current?.readyState === WebSocket.OPEN)
      wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: isTypingNow }));
  }, []);

  return { messages, sendMessage, sendFileMessage, sendTyping, isConnected, isTyping, currentUserId: user?.id };
}
