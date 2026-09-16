import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, Wifi, WifiOff, Loader2, Pill, X, CheckCircle, XCircle,
  Paperclip, Mic, StopCircle, Download, FileText, Volume2, Phone, Video, ClipboardList,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth.store';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { axiosInstance } from '@/lib/axios';
import CallModal from '@/components/communications/CallModal';
import { useCreateDigitalPrescription } from '@/hooks/useDoctor';
import { useRequestAdherenceReport, useRespondAdherenceRequest } from '@/hooks/useDoctorConsultation';

const _apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE  = new URL(_apiUrl).origin.replace(/^http/, 'ws');

const STATUS_COLORS = {
  REQUESTED: 'warning', ACCEPTED: 'primary',
  ACTIVE: 'success', COMPLETED: 'secondary', REJECTED: 'danger',
};

// ─── WebSocket hook ───────────────────────────────────────────────────────────
function useDoctorChatSocket(sessionId) {
  const token = useAuthStore((s) => s.accessToken);
  const user  = useAuthStore((s) => s.user);

  const [messages,    setMessages]    = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTyping,    setIsTyping]    = useState(false);

  const wsRef          = useRef(null);
  const typingTimerRef = useRef(null);

  useEffect(() => {
    if (!sessionId || !token) return;
    const ws = new WebSocket(`${WS_BASE}/ws/doctor-chat/${sessionId}/?token=${token}`);
    wsRef.current = ws;
    ws.onopen  = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const CARD_TYPES = ['message', 'file', 'adherence_request', 'adherence_report', 'prescription'];
        if (data.type === 'history') {
          setMessages(data.messages || []);
        } else if (CARD_TYPES.includes(data.type)) {
          setMessages((prev) => [...prev, data]);
        } else if (data.type === 'typing') {
          setIsTyping(data.is_typing);
          if (data.is_typing) {
            clearTimeout(typingTimerRef.current);
            typingTimerRef.current = setTimeout(() => setIsTyping(false), 3000);
          }
        }
      } catch {}
    };
    return () => { ws.close(); clearTimeout(typingTimerRef.current); };
  }, [sessionId, token]);

  const sendMessage     = useCallback((content) => wsRef.current?.readyState === WebSocket.OPEN && wsRef.current.send(JSON.stringify({ type: 'message', content })), []);
  const sendFileMessage = useCallback((info)    => wsRef.current?.readyState === WebSocket.OPEN && wsRef.current.send(JSON.stringify({ type: 'file', ...info })), []);
  const sendTyping      = useCallback((v)       => wsRef.current?.readyState === WebSocket.OPEN && wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: v })), []);

  return { messages, sendMessage, sendFileMessage, sendTyping, isConnected, isTyping, currentUserId: user?.id };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmtTime(iso) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
}
function fmtBytes(b) {
  if (!b) return '';
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}
function dateLabel(iso) {
  try {
    const d   = new Date(iso);
    const now = new Date();
    const yes = new Date(now); yes.setDate(yes.getDate() - 1);
    if (d.toDateString() === now.toDateString()) return 'Today';
    if (d.toDateString() === yes.toDateString()) return 'Yesterday';
    return d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return ''; }
}
function needsSeparator(msgs, idx) {
  if (idx === 0) return true;
  try {
    const a = new Date(msgs[idx - 1].created_at).toDateString();
    const b = new Date(msgs[idx].created_at).toDateString();
    return a !== b;
  } catch { return false; }
}

// ─── Date separator ───────────────────────────────────────────────────────────
function DateSep({ label }) {
  return (
    <div className="flex items-center justify-center my-3">
      <span className="text-[11px] font-semibold text-muted-foreground bg-background/80 backdrop-blur-sm border border-border/40 px-3 py-1 rounded-full shadow-sm">
        {label}
      </span>
    </div>
  );
}

// ─── Tick icon (message status) ───────────────────────────────────────────────
function Ticks({ isRead }) {
  return (
    <span className={`inline-flex ml-1 ${isRead ? 'text-sky-400' : 'opacity-50'}`} style={{ fontSize: 11 }}>
      {isRead ? '✓✓' : '✓'}
    </span>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────────
function Bubble({ msg }) {
  const own    = msg.is_own;
  const isFile = msg.type === 'file';
  const mime   = msg.mime_type || '';
  const isImg  = mime.startsWith('image/');
  const isAud  = mime.startsWith('audio/');
  const time   = fmtTime(msg.created_at);

  // Tail: own → bottom-right flat; other → bottom-left flat
  const bubbleCls = own
    ? 'bg-primary text-primary-foreground rounded-2xl rounded-br-sm ml-auto'
    : 'bg-card border border-border/60 text-foreground rounded-2xl rounded-bl-sm mr-auto';

  const metaCls = own
    ? 'text-primary-foreground/60 justify-end'
    : 'text-muted-foreground';

  return (
    <div className={`flex flex-col max-w-[72%] ${own ? 'items-end self-end' : 'items-start self-start'}`}>
      {/* Sender name (only on received) */}
      {!own && msg.sender_name && (
        <span className="text-[10px] font-bold text-primary ml-3 mb-0.5">{msg.sender_name}</span>
      )}

      <div className={`${bubbleCls} shadow-sm overflow-hidden`}>
        {/* Plain text */}
        {!isFile && (
          <div className="px-3.5 pt-2 pb-1.5">
            <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
            <div className={`flex items-center gap-0.5 text-[10px] mt-1 ${metaCls}`}>
              <span>{time}</span>
              {own && <Ticks isRead={msg.is_read} />}
            </div>
          </div>
        )}

        {/* Image */}
        {isFile && isImg && (
          <div>
            <img
              src={msg.file_url} alt={msg.file_name || 'image'}
              className="max-w-[260px] max-h-[280px] object-cover block cursor-pointer"
              onClick={() => window.open(msg.file_url, '_blank')}
            />
            <div className={`flex items-center justify-between px-3 py-1.5 gap-3 ${own ? 'bg-primary/80' : ''}`}>
              <span className="text-[10px] truncate max-w-[140px] opacity-70">{msg.file_name}</span>
              <div className={`flex items-center gap-1.5 flex-shrink-0 text-[10px] ${metaCls}`}>
                <span>{time}</span>
                {own && <Ticks isRead={msg.is_read} />}
                <a href={msg.file_url} download={msg.file_name} className="opacity-70 hover:opacity-100"><Download className="w-3 h-3" /></a>
              </div>
            </div>
          </div>
        )}

        {/* Voice note */}
        {isFile && isAud && (
          <div className="px-3.5 pt-2.5 pb-2 min-w-[220px]">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${own ? 'bg-white/20' : 'bg-primary/10'}`}>
                <Volume2 className={`w-4 h-4 ${own ? 'text-white' : 'text-primary'}`} />
              </div>
              <div className="flex-1">
                <p className="text-xs font-semibold leading-none">Voice Note</p>
                <p className="text-[10px] opacity-60 mt-0.5">{fmtBytes(msg.file_size)}</p>
              </div>
              <a href={msg.file_url} download={msg.file_name || 'voice.webm'} className="opacity-60 hover:opacity-100">
                <Download className="w-3.5 h-3.5" />
              </a>
            </div>
            <audio controls src={msg.file_url} className="w-full h-7 rounded" style={{ minWidth: 190 }} />
            <div className={`flex items-center gap-0.5 text-[10px] mt-1.5 ${metaCls}`}>
              <span>{time}</span>{own && <Ticks isRead={msg.is_read} />}
            </div>
          </div>
        )}

        {/* Generic file */}
        {isFile && !isImg && !isAud && (
          <div className="px-3.5 py-2.5 flex items-center gap-3 min-w-[200px]">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${own ? 'bg-white/20' : 'bg-primary/10'}`}>
              <FileText className={`w-5 h-5 ${own ? 'text-white' : 'text-primary'}`} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{msg.file_name || 'File'}</p>
              <p className="text-[10px] opacity-60">{fmtBytes(msg.file_size)}</p>
            </div>
            <a href={msg.file_url} download={msg.file_name} className="opacity-60 hover:opacity-100 flex-shrink-0">
              <Download className="w-4 h-4" />
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Structured cards (adherence request/report, prescription) ───────────────
function AdherenceRequestCard({ msg, isDoctor, onRespond, responding }) {
  const status = msg.metadata?.status || 'PENDING';
  return (
    <div className="max-w-[85%] self-start bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 shadow-sm">
      <p className="text-xs font-bold text-amber-800 mb-1 flex items-center gap-1.5">
        <ClipboardList className="w-3.5 h-3.5" /> Adherence Report Request
      </p>
      <p className="text-xs text-amber-700">{msg.content}</p>
      {!isDoctor && status === 'PENDING' ? (
        <div className="flex gap-2 mt-2">
          <Button size="sm" className="h-7 text-xs flex-1" disabled={responding}
            onClick={() => onRespond(msg.metadata.request_id, true)}>Approve</Button>
          <Button size="sm" variant="outline" className="h-7 text-xs flex-1" disabled={responding}
            onClick={() => onRespond(msg.metadata.request_id, false)}>Deny</Button>
        </div>
      ) : (
        <Badge variant={status === 'APPROVED' ? 'success' : status === 'DENIED' ? 'danger' : 'warning'}
          className="mt-2 text-[9px] font-black uppercase">{status}</Badge>
      )}
    </div>
  );
}

function AdherenceReportCard({ msg }) {
  const report = msg.metadata?.report || {};
  const entries = Object.entries(report).filter(([, v]) => v !== null && typeof v !== 'object');
  return (
    <div className="max-w-[85%] self-start bg-emerald-50 border border-emerald-200 rounded-2xl px-4 py-3 shadow-sm">
      <p className="text-xs font-bold text-emerald-800 mb-2">📊 Adherence Report (last 30 days)</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-emerald-900">
        {entries.map(([k, v]) => (
          <div key={k} className="truncate">
            <span className="opacity-60 capitalize">{k.replace(/_/g, ' ')}:</span> <b>{String(v)}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function PrescriptionCard({ msg }) {
  const meta   = msg.metadata || {};
  const points = meta.instruction_points || [];
  return (
    <div className="max-w-[85%] self-start bg-primary/5 border border-primary/20 rounded-2xl px-4 py-3 shadow-sm">
      <p className="text-xs font-bold text-primary mb-1 flex items-center gap-1.5">
        <Pill className="w-3.5 h-3.5" /> {meta.medication_name} {meta.dosage ? `(${meta.dosage})` : ''}
      </p>
      {points.length > 0 && (
        <ul className="text-xs text-foreground list-disc list-inside space-y-0.5 mt-1">
          {points.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}
    </div>
  );
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingBubble({ name }) {
  return (
    <div className="flex items-end gap-2 self-start mb-2">
      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs font-bold flex-shrink-0">
        {(name || '?')[0].toUpperCase()}
      </div>
      <div className="bg-card border border-border/60 px-4 py-3 rounded-2xl rounded-bl-sm shadow-sm">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span key={i} className="w-1.5 h-1.5 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function DoctorChatRoom({ session, isDoctor = false, onEnd, onClose }) {
  const [input,         setInput]         = useState('');
  const [rxMedName,     setRxMedName]     = useState('');
  const [rxDosage,      setRxDosage]      = useState('');
  const [rxPointsText,  setRxPointsText]  = useState('');
  const [showPrescForm, setShowPrescForm] = useState(false);
  const [endNotes,      setEndNotes]      = useState('');
  const [showEndForm,   setShowEndForm]   = useState(false);
  const [uploading,     setUploading]     = useState(false);
  const [recording,     setRecording]     = useState(false);
  const [callOpen,      setCallOpen]      = useState(false);
  const [callVideo,     setCallVideo]     = useState(false);

  const messagesEndRef = useRef(null);
  const typingTimerRef = useRef(null);
  const fileInputRef   = useRef(null);
  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);

  const { messages, sendMessage, sendFileMessage, sendTyping, isConnected, isTyping } =
    useDoctorChatSocket(session?.id);

  const createPrescription  = useCreateDigitalPrescription();
  const requestAdherence    = useRequestAdherenceReport();
  const respondAdherence    = useRespondAdherenceRequest();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Text ──────────────────────────────────────────────────────────────────
  const handleSend = () => {
    const text = input.trim();
    if (!text || !isConnected) return;
    sendMessage(text);
    setInput('');
    sendTyping(false);
    clearTimeout(typingTimerRef.current);
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    sendTyping(true);
    clearTimeout(typingTimerRef.current);
    typingTimerRef.current = setTimeout(() => sendTyping(false), 2000);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // ── File upload ───────────────────────────────────────────────────────────
  const uploadFile = async (blob, fileName, mimeType) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', blob, fileName);
      const res = await axiosInstance.post(
        `/doctor/consultations/${session?.id}/upload/`,
        form, { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      const { file_url, file_name, file_size } = res.data?.data || res.data || {};
      sendFileMessage({ file_url, file_name: file_name || fileName, file_size: file_size || blob.size, mime_type: mimeType });
    } catch (err) { console.error('Upload failed:', err); }
    finally { setUploading(false); }
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    uploadFile(f, f.name, f.type || 'application/octet-stream');
    e.target.value = '';
  };

  // ── Voice note ────────────────────────────────────────────────────────────
  const startRec = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecRef.current = mr;
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const ts   = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-');
        uploadFile(blob, `voice-${ts}.webm`, 'audio/webm');
      };
      mr.start();
      setRecording(true);
    } catch { console.error('Mic denied'); }
  };

  const stopRec  = () => { mediaRecRef.current?.stop(); setRecording(false); };
  const toggleRec = () => { recording ? stopRec() : startRec(); };

  // ── Session end ───────────────────────────────────────────────────────────
  const handleEnd = () => { if (onEnd) onEnd(endNotes); setShowEndForm(false); };

  // ── Point-wise prescription (posted via REST; server drops a chat card + notifies) ──
  const handleSendPrescription = async () => {
    const points = rxPointsText.split('\n').map((p) => p.trim()).filter(Boolean);
    if (!rxMedName.trim() || points.length === 0) return;
    try {
      await createPrescription.mutateAsync({
        patient: session?.patient,
        session: session?.id,
        medication_name: rxMedName.trim(),
        dosage: rxDosage.trim() || 'As directed',
        instruction_points: points,
        start_date: new Date().toISOString().slice(0, 10),
      });
      setRxMedName(''); setRxDosage(''); setRxPointsText(''); setShowPrescForm(false);
    } catch (err) { console.error('Prescription failed:', err); }
  };

  // ── Adherence report request/approval (chat AND call) ─────────────────────
  const handleRequestAdherence = () => {
    requestAdherence.mutate(session?.id);
  };
  const handleRespondAdherence = (requestId, approved) => {
    respondAdherence.mutate({ sessionId: session?.id, requestId, approved });
  };

  const otherName   = isDoctor ? (session?.patient_name || 'Patient') : (session?.doctor_name || 'Doctor');
  const isActive    = ['ACTIVE', 'ACCEPTED'].includes(session?.status);
  const isRequested = session?.status === 'REQUESTED';
  const isCompleted = session?.status === 'COMPLETED';

  return (
    <div className="flex flex-col h-full bg-background overflow-hidden rounded-[2rem] border border-border/50 shadow-xl">

      {/* ── Header (WhatsApp-style) ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-primary/5 flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* Avatar with online dot */}
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center text-white text-sm font-bold shadow">
              {otherName.slice(0, 2).toUpperCase()}
            </div>
            {isActive && (
              <span className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-400 rounded-full border-2 border-background" />
            )}
          </div>
          <div>
            <p className="font-bold text-sm text-foreground leading-none">{otherName}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
              {isConnected
                ? <><span className="w-1.5 h-1.5 bg-emerald-400 rounded-full inline-block" />online</>
                : <><WifiOff className="w-3 h-3" />connecting…</>
              }
              {session?.status && (
                <Badge variant={STATUS_COLORS[session.status] || 'secondary'} className="h-4 px-1.5 text-[8px] font-black uppercase ml-1">
                  {session.status}
                </Badge>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isActive && (
            <>
              <button onClick={() => { setCallVideo(false); setCallOpen(true); }} title="Voice Call"
                className="w-9 h-9 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 flex items-center justify-center transition-colors">
                <Phone className="w-4 h-4" />
              </button>
              <button onClick={() => { setCallVideo(true); setCallOpen(true); }} title="Video Call"
                className="w-9 h-9 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary flex items-center justify-center transition-colors">
                <Video className="w-4 h-4" />
              </button>
            </>
          )}
          {isDoctor && isActive && (
            <Button variant="danger" size="sm" className="h-8 px-3 text-[10px] font-black uppercase rounded-lg" onClick={() => setShowEndForm(true)}>
              End
            </Button>
          )}
          {onClose && (
            <button onClick={onClose} className="p-2 rounded-xl hover:bg-muted transition-colors">
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      {/* ── Waiting for acceptance banner ────────────────────────────────────── */}
      {isRequested && (
        <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-200 flex-shrink-0 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
          <p className="text-xs font-semibold text-amber-700">
            {isDoctor
              ? 'Patient is waiting — accept this request to start chatting.'
              : 'Consultation request sent. Waiting for the doctor to accept…'}
          </p>
        </div>
      )}

      {/* ── End session form ──────────────────────────────────────────────────── */}
      {showEndForm && (
        <div className="px-4 py-3 bg-destructive/5 border-b border-destructive/20 flex-shrink-0">
          <p className="text-xs font-bold text-destructive mb-2">End session — add optional notes:</p>
          <textarea value={endNotes} onChange={(e) => setEndNotes(e.target.value)} placeholder="Diagnosis, follow-up…" rows={2}
            className="w-full resize-none rounded-xl border border-destructive/30 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-destructive/30 mb-2" />
          <div className="flex gap-2">
            <Button size="sm" variant="danger"   className="h-8 flex-1" onClick={handleEnd}><CheckCircle className="w-3.5 h-3.5 mr-1" /> Confirm</Button>
            <Button size="sm" variant="outline"  className="h-8 flex-1" onClick={() => setShowEndForm(false)}><XCircle className="w-3.5 h-3.5 mr-1" /> Cancel</Button>
          </div>
        </div>
      )}

      {/* ── Prescription + adherence-request shortcuts (doctor only) ─────────── */}
      {isDoctor && isActive && !showEndForm && (
        <div className="px-4 pt-2 flex-shrink-0">
          {showPrescForm ? (
            <div className="p-3 rounded-xl bg-primary/5 border border-primary/20 mb-2 space-y-2">
              <div className="flex gap-2">
                <input value={rxMedName} onChange={(e) => setRxMedName(e.target.value)} placeholder="Medicine name"
                  className="flex-1 rounded-lg border border-primary/20 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
                <input value={rxDosage} onChange={(e) => setRxDosage(e.target.value)} placeholder="Dosage (e.g. 500mg)"
                  className="flex-1 rounded-lg border border-primary/20 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
              </div>
              <textarea value={rxPointsText} onChange={(e) => setRxPointsText(e.target.value)}
                placeholder={'Instructions, one point per line:\nTake after food\nAvoid alcohol'} rows={3}
                className="w-full resize-none rounded-lg border border-primary/20 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
              <div className="flex gap-2">
                <Button size="sm" className="h-7 flex-1 text-xs" disabled={createPrescription.isPending} onClick={handleSendPrescription}>
                  {createPrescription.isPending ? 'Sending…' : 'Send Prescription'}
                </Button>
                <Button size="sm" variant="ghost" className="h-7 flex-1 text-xs" onClick={() => setShowPrescForm(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2 mb-2">
              <button onClick={() => setShowPrescForm(true)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-primary/5 hover:bg-primary/10 transition-colors text-primary">
                <Pill className="w-3.5 h-3.5" />
                <span className="text-xs font-bold">Add Prescription</span>
              </button>
              <button onClick={handleRequestAdherence} disabled={requestAdherence.isPending}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-amber-500/5 hover:bg-amber-500/10 transition-colors text-amber-600 disabled:opacity-50">
                <ClipboardList className="w-3.5 h-3.5" />
                <span className="text-xs font-bold">{requestAdherence.isPending ? 'Requesting…' : 'Request Adherence Report'}</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Message area (WhatsApp background) ──────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0 px-4 py-3 flex flex-col gap-1.5"
        style={{ background: 'var(--chat-bg, #f0f4f8)' }}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
              <span className="text-3xl">💬</span>
            </div>
            <p className="text-sm font-semibold text-foreground">No messages yet</p>
            <p className="text-xs text-muted-foreground">Start the conversation with {otherName}</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={msg.id || i} className="flex flex-col">
              {needsSeparator(messages, i) && <DateSep label={dateLabel(msg.created_at)} />}
              {msg.type === 'adherence_request' ? (
                <AdherenceRequestCard msg={msg} isDoctor={isDoctor} onRespond={handleRespondAdherence} responding={respondAdherence.isPending} />
              ) : msg.type === 'adherence_report' ? (
                <AdherenceReportCard msg={msg} />
              ) : msg.type === 'prescription' ? (
                <PrescriptionCard msg={msg} />
              ) : (
                <Bubble msg={msg} />
              )}
            </div>
          ))
        )}

        {isTyping && <TypingBubble name={otherName} />}

        {uploading && (
          <div className="self-end flex items-center gap-2 bg-primary/10 px-4 py-2.5 rounded-2xl rounded-br-sm mb-1">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            <span className="text-xs text-primary font-medium">Sending…</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Input bar (WhatsApp-style) ─────────────────────────────────────── */}
      <div className="px-3 py-3 border-t border-border bg-background flex-shrink-0">
        {isCompleted ? (
          <div className="flex items-center justify-center py-2 gap-2 text-muted-foreground">
            <span className="text-xs font-medium">Session ended — messages are read-only.</span>
          </div>
        ) : isRequested && !isDoctor ? (
          /* Patient waiting view — input visible but disabled with hint */
          <div className="flex items-center gap-3 px-4 py-3 bg-muted/40 rounded-2xl mx-1">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
            <p className="text-xs text-muted-foreground font-medium">Waiting for {otherName} to accept your request before you can chat…</p>
          </div>
        ) : isRequested && isDoctor ? (
          /* Doctor view — prompt to accept */
          <div className="flex items-center gap-3 px-4 py-3 bg-amber-50 rounded-2xl mx-1 border border-amber-200">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
            <p className="text-xs text-amber-700 font-semibold flex-1">Accept the request above to begin chatting with {otherName}.</p>
          </div>
        ) : (
          <>
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileChange}
              accept="image/*,application/pdf,.doc,.docx,.txt,.xls,.xlsx,.csv,audio/*" />

            <div className="flex items-end gap-2">
              {/* Attach */}
              <button onClick={() => fileInputRef.current?.click()} disabled={!isConnected || uploading} title="Attach file"
                className="w-10 h-10 rounded-full bg-muted hover:bg-muted/70 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40 flex-shrink-0">
                <Paperclip className="w-5 h-5" />
              </button>

              {/* Text input */}
              <div className="flex-1 bg-muted/50 border border-border/60 rounded-3xl px-4 py-2.5 flex items-end">
                <textarea
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={isConnected ? `Message ${otherName}…` : 'Connecting…'}
                  disabled={!isConnected || !isActive}
                  rows={1}
                  className="w-full resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 max-h-28"
                  style={{ minHeight: '22px' }}
                />
              </div>

              {/* Mic or Send */}
              {input.trim() ? (
                <button onClick={handleSend} disabled={!isConnected || !isActive}
                  className="w-10 h-10 rounded-full bg-primary hover:bg-primary/90 flex items-center justify-center text-white transition-colors disabled:opacity-40 flex-shrink-0 shadow-md">
                  <Send className="w-4 h-4" />
                </button>
              ) : (
                <button onClick={toggleRec} disabled={!isConnected || !isActive || uploading} title={recording ? 'Stop' : 'Voice note'}
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-all disabled:opacity-40 flex-shrink-0 shadow-md ${
                    recording ? 'bg-destructive text-white animate-pulse' : 'bg-primary text-white hover:bg-primary/90'
                  }`}>
                  {recording ? <StopCircle className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              )}
            </div>

            {recording && (
              <div className="flex items-center gap-2 mt-2 px-1">
                <span className="w-2 h-2 rounded-full bg-destructive animate-ping" />
                <span className="text-xs text-destructive font-semibold">Recording… tap stop when done</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Call modal — scoped to this consultation session (gated server-side on
          the doctor's availability + live presence, see DoctorCallConsumer) */}
      {callOpen && (
        <CallModal
          roomId={session?.id}
          wsPath="doctor-call"
          video={callVideo}
          patientName={otherName}
          onClose={() => setCallOpen(false)}
          actions={isDoctor ? [
            { icon: Pill, label: 'Prescription', onClick: () => { setShowPrescForm(true); setCallOpen(false); } },
            { icon: ClipboardList, label: 'Adherence Report', onClick: handleRequestAdherence },
          ] : []}
        />
      )}
    </div>
  );
}
