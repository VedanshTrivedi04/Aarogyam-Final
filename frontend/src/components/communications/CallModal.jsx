import { useState, useEffect, useRef } from 'react';
import { Phone, PhoneOff, Mic, MicOff, Video, VideoOff, Loader2 } from 'lucide-react';
import { useCallSocket } from '@/hooks/useCallSocket';
import { caregiverAgent } from '@/agents/caregiver.agent';

function CallTimer({ active }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) { setSeconds(0); return; }
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [active]);
  const m = String(Math.floor(seconds / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return <span className="text-white/70 text-sm font-mono">{m}:{s}</span>;
}

/**
 * CallModal — reusable for both caregiver<->patient calls (default) and
 * doctor<->patient calls.
 *
 * - Caregiver mode (default): pass `patientId` — the room is looked up/created
 *   via the caregiver chat-room API, signaling goes over ws/call/.
 * - Doctor mode: pass `roomId` directly (the ConsultationSession id) and
 *   `wsPath="doctor-call"` — signaling goes over ws/doctor-call/, which the
 *   server gates on the doctor's availability + live presence.
 * - `video`: request a camera track and render video elements (voice-only otherwise).
 * - `actions`: optional [{ icon, label, onClick }] — extra buttons shown during
 *   an active call (e.g. doctor's "Add Prescription" / "Request Adherence Report").
 */
export default function CallModal({
  patientId, patientName, roomId: roomIdProp, wsPath = 'call', video = false,
  onClose, onCallError, actions = [],
}) {
  const [roomId,  setRoomId]  = useState(roomIdProp || null);
  const [muted,   setMuted]   = useState(false);
  const [videoOff, setVideoOff] = useState(false);
  const [loading, setLoading] = useState(!roomIdProp);
  const [errorMsg, setErrorMsg] = useState(null);

  const remoteAudioRef = useRef(null);
  const localVideoRef  = useRef(null);
  const remoteVideoRef = useRef(null);

  const { callState, isConnected, localStream, remoteStream, peerInfo, startCall, answerCall, endCall } =
    useCallSocket(roomId, {
      wsPath, video,
      onCallEnded:   () => { onClose(); },
      onCallStarted: () => {},
      onCallError:   (err) => {
        setErrorMsg(err?.reason === 'doctor_unavailable'
          ? 'Doctor is not available for a call right now.'
          : 'Could not start the call.');
        onCallError?.(err);
      },
    });

  const displayName = peerInfo?.name || patientName;

  // Caregiver mode: get/create the room first. Doctor mode: roomId is given directly.
  useEffect(() => {
    if (roomIdProp) return;
    caregiverAgent.getOrCreateChatRoom(patientId)
      .then((res) => setRoomId(res?.id || res?.data?.id))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [patientId, roomIdProp]);

  // Initiate call once WS is connected and we have a room
  useEffect(() => {
    if (isConnected && callState === 'idle' && roomId) {
      startCall();
    }
  }, [isConnected, callState, roomId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Attach remote stream to audio/video elements
  useEffect(() => {
    if (remoteAudioRef.current && remoteStream) {
      remoteAudioRef.current.srcObject = remoteStream;
    }
    if (remoteVideoRef.current && remoteStream) {
      remoteVideoRef.current.srcObject = remoteStream;
    }
  }, [remoteStream]);

  useEffect(() => {
    if (localVideoRef.current && localStream) {
      localVideoRef.current.srcObject = localStream;
    }
  }, [localStream]);

  // Mute/unmute local stream
  useEffect(() => {
    localStream?.getAudioTracks().forEach((t) => { t.enabled = !muted; });
  }, [muted, localStream]);

  useEffect(() => {
    localStream?.getVideoTracks().forEach((t) => { t.enabled = !videoOff; });
  }, [videoOff, localStream]);

  const handleEnd = () => {
    endCall();
    onClose();
  };

  const stateLabel = errorMsg ? errorMsg : ({
    idle:    'Connecting…',
    ringing: 'Ringing…',
    active:  'In Call',
    ended:   'Call Ended',
  }[callState] ?? 'Connecting…');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-80 bg-gradient-to-br from-slate-800 to-slate-900 rounded-[2.5rem] shadow-2xl overflow-hidden">
        {/* Background pulse when ringing */}
        {callState === 'ringing' && (
          <div className="absolute inset-0 animate-pulse bg-primary/10 pointer-events-none" />
        )}

        <div className="flex flex-col items-center px-8 pt-12 pb-10 gap-6">
          {/* Video streams (video mode + active call only) */}
          {video && callState === 'active' && (
            <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-black">
              <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
              <video ref={localVideoRef} autoPlay playsInline muted
                className="absolute bottom-2 right-2 w-20 h-16 rounded-lg object-cover border-2 border-white/30" />
            </div>
          )}

          {/* Avatar (shown when not in an active video call) */}
          {!(video && callState === 'active') && (
            <div className="relative">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-3xl font-bold shadow-xl">
                {(displayName || '?').slice(0, 2).toUpperCase()}
              </div>
              {callState === 'active' && (
                <span className="absolute bottom-1 right-1 w-4 h-4 bg-emerald-400 rounded-full border-2 border-slate-900" />
              )}
            </div>
          )}

          {/* Name + state */}
          <div className="text-center">
            <h2 className="text-white text-xl font-bold">{displayName}</h2>
            <div className="flex items-center justify-center gap-2 mt-1">
              {(loading || callState === 'idle') && !errorMsg && <Loader2 className="w-3.5 h-3.5 text-white/50 animate-spin" />}
              <p className={`text-sm ${errorMsg ? 'text-red-400' : 'text-white/60'}`}>{loading ? 'Connecting…' : stateLabel}</p>
            </div>
            <CallTimer active={callState === 'active'} />
          </div>

          {/* Ringing — show answer button for the other party */}
          {callState === 'ringing' && (
            <button
              onClick={answerCall}
              className="w-14 h-14 rounded-full bg-emerald-500 hover:bg-emerald-400 flex items-center justify-center shadow-lg transition-colors"
            >
              <Phone className="w-6 h-6 text-white" />
            </button>
          )}

          {/* Extra actions (e.g. doctor's prescription / adherence-report buttons) */}
          {callState === 'active' && actions.length > 0 && (
            <div className="flex items-center gap-2 -mt-2">
              {actions.map((a, i) => (
                <button key={i} onClick={a.onClick} title={a.label}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white text-[11px] font-semibold transition-colors">
                  {a.icon && <a.icon className="w-3.5 h-3.5" />}
                  {a.label}
                </button>
              ))}
            </div>
          )}

          {/* Controls */}
          <div className="flex items-center gap-6">
            <button
              onClick={() => setMuted((m) => !m)}
              disabled={callState !== 'active'}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors disabled:opacity-30 ${
                muted ? 'bg-red-500/20 text-red-400' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {muted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>

            {video && (
              <button
                onClick={() => setVideoOff((v) => !v)}
                disabled={callState !== 'active'}
                className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors disabled:opacity-30 ${
                  videoOff ? 'bg-red-500/20 text-red-400' : 'bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                {videoOff ? <VideoOff className="w-5 h-5" /> : <Video className="w-5 h-5" />}
              </button>
            )}

            <button
              onClick={handleEnd}
              className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-400 flex items-center justify-center shadow-xl transition-colors"
            >
              <PhoneOff className="w-6 h-6 text-white" />
            </button>
          </div>
        </div>
      </div>

      {/* Hidden audio element — only needed for voice-only calls; in video
          mode the remote <video> tag above already carries the audio track. */}
      {!video && <audio ref={remoteAudioRef} autoPlay playsInline className="hidden" />}
    </div>
  );
}
