import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/auth.store';

// Extract only origin (strips /api/v1 or any path suffix from VITE_API_URL)
const _apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE = new URL(_apiUrl).origin.replace(/^http/, 'ws');

const ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
];

/**
 * useCallSocket(roomId, { onCallEnded, onCallStarted, onCallError, wsPath, video, peerInfo })
 * Manages WebRTC signaling via Django Channels.
 *
 * - `wsPath`: which signaling channel to use — 'call' (caregiver<->patient,
 *   default) or 'doctor-call' (doctor<->patient, gated on doctor
 *   availability/presence server-side).
 * - `video`: request a camera track in addition to the mic (voice-only when false).
 * - `onCallError`: called with { reason } if the server rejects the call
 *   (e.g. 'doctor_unavailable') instead of relaying it.
 *
 * Returns: { callState, startCall, answerCall, endCall, localStream, remoteStream, peerInfo }
 * callState: 'idle' | 'ringing' | 'active' | 'ended'
 */
export function useCallSocket(roomId, {
  onCallEnded, onCallStarted, onCallError, wsPath = 'call', video = false,
} = {}) {
  const token = useAuthStore((s) => s.accessToken);
  const user  = useAuthStore((s) => s.user);

  const [callState,    setCallState]    = useState('idle');
  const [localStream,  setLocalStream]  = useState(null);
  const [remoteStream, setRemoteStream] = useState(null);
  const [isConnected,  setIsConnected]  = useState(false);
  const [peerInfo,     setPeerInfo]     = useState(null);

  const wsRef  = useRef(null);
  const pcRef  = useRef(null);  // RTCPeerConnection

  // ── Cleanup helper ────────────────────────────────────────────────────────
  const cleanup = useCallback(() => {
    pcRef.current?.close();
    pcRef.current = null;
    localStream?.getTracks().forEach((t) => t.stop());
    setLocalStream(null);
    setRemoteStream(null);
    setCallState('idle');
  }, [localStream]);

  // ── WebSocket setup ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!roomId || !token) return;

    const url = `${WS_BASE}/ws/${wsPath}/${roomId}/?token=${token}`;
    const ws  = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen  = () => setIsConnected(true);
    ws.onclose = () => { setIsConnected(false); cleanup(); };

    ws.onmessage = async (e) => {
      try {
        const data = JSON.parse(e.data);
        await handleSignal(data);
      } catch {}
    };

    return () => ws.close();
  }, [roomId, token, wsPath]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = useCallback((payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  // ── WebRTC helpers ────────────────────────────────────────────────────────
  const createPeerConnection = useCallback((stream) => {
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    pcRef.current = pc;

    stream.getTracks().forEach((t) => pc.addTrack(t, stream));

    pc.onicecandidate = (e) => {
      if (e.candidate) {
        send({ type: 'ice_candidate', candidate: e.candidate });
      }
    };

    pc.ontrack = (e) => {
      setRemoteStream(e.streams[0]);
    };

    return pc;
  }, [send]);

  // ── Signal handler ────────────────────────────────────────────────────────
  const handleSignal = useCallback(async (data) => {
    switch (data.type) {
      case 'peer_joined':
        // Other party connected — carries their profile details (see
        // DoctorCallConsumer._peer_join_info) so the ringing screen can show
        // who's calling before the offer/answer even happens.
        if (data.patient || data.doctor) {
          setPeerInfo(data.patient || data.doctor);
        }
        break;

      case 'call_error':
        setCallState('idle');
        onCallError?.({ reason: data.reason });
        break;

      case 'call_offer': {
        setCallState('ringing');
        // Store the offer; answerCall() will use it
        pcRef._pendingOffer = data.sdp;
        break;
      }

      case 'call_answer': {
        if (pcRef.current) {
          await pcRef.current.setRemoteDescription({ type: 'answer', sdp: data.sdp });
          setCallState('active');
          onCallStarted?.();
        }
        break;
      }

      case 'ice_candidate': {
        if (pcRef.current && data.candidate) {
          try {
            await pcRef.current.addIceCandidate(data.candidate);
          } catch {}
        }
        break;
      }

      case 'call_end':
        cleanup();
        onCallEnded?.();
        break;

      default:
        break;
    }
  }, [cleanup, onCallEnded, onCallStarted, onCallError]);

  // ── Public API ────────────────────────────────────────────────────────────

  const startCall = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video });
      setLocalStream(stream);
      const pc = createPeerConnection(stream);

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      send({ type: 'call_offer', sdp: offer.sdp });
      setCallState('ringing');
    } catch (err) {
      console.error('startCall failed:', err);
      cleanup();
    }
  }, [createPeerConnection, send, cleanup, video]);

  const answerCall = useCallback(async () => {
    try {
      const pendingOffer = pcRef._pendingOffer;
      if (!pendingOffer) return;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video });
      setLocalStream(stream);
      const pc = createPeerConnection(stream);

      await pc.setRemoteDescription({ type: 'offer', sdp: pendingOffer });
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      send({ type: 'call_answer', sdp: answer.sdp });
      setCallState('active');
      onCallStarted?.();
    } catch (err) {
      console.error('answerCall failed:', err);
      cleanup();
    }
  }, [createPeerConnection, send, cleanup, onCallStarted, video]);

  const endCall = useCallback(() => {
    send({ type: 'call_end' });
    cleanup();
    onCallEnded?.();
  }, [send, cleanup, onCallEnded]);

  return {
    callState,
    isConnected,
    localStream,
    remoteStream,
    peerInfo,
    startCall,
    answerCall,
    endCall,
    currentUserId: user?.id,
  };
}
