import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare, Clock, CheckCircle2, XCircle, Loader2,
  ChevronRight, Stethoscope, History, Inbox,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  useConsultations,
  useAcceptConsultation,
  useRejectConsultation,
  useEndConsultation,
} from '@/hooks/useDoctorConsultation';
import DoctorChatRoom from '@/components/doctor/DoctorChatRoom';

const STATUS_BADGE = {
  REQUESTED: { variant: 'warning',   label: 'Pending' },
  ACCEPTED:  { variant: 'primary',   label: 'Accepted' },
  ACTIVE:    { variant: 'success',   label: 'Active' },
  COMPLETED: { variant: 'secondary', label: 'Completed' },
  REJECTED:  { variant: 'danger',    label: 'Rejected' },
};

function SessionRow({ session, onOpen, onAccept, onReject, acceptPending, rejectPending }) {
  const badge = STATUS_BADGE[session.status] || { variant: 'secondary', label: session.status };
  const isRequested = session.status === 'REQUESTED';
  const isActive    = session.status === 'ACTIVE' || session.status === 'ACCEPTED';

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-5 rounded-2xl border border-border/50 bg-card hover:bg-muted/10 transition-colors">
      <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary font-bold text-xl flex-shrink-0">
        {(session.patient_name || 'P')[0].toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-0.5">
          <h4 className="font-bold text-foreground">{session.patient_name || 'Patient'}</h4>
          <Badge variant={badge.variant} className="h-4 px-2 text-[9px] font-black uppercase">{badge.label}</Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Code: {session.patient_code || '—'}
          {session.requested_at && ` · Requested ${new Date(session.requested_at).toLocaleDateString()}`}
        </p>
        {session.last_message?.content && (
          <p className="text-xs text-muted-foreground truncate mt-1 italic">"{session.last_message.content}"</p>
        )}
      </div>

      <div className="flex gap-2 flex-shrink-0">
        {isRequested && (
          <>
            <Button
              size="sm"
              className="h-9 px-4 rounded-xl text-xs font-black"
              onClick={() => onAccept(session.id)}
              disabled={acceptPending}
            >
              {acceptPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 mr-1" />}
              Accept
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-9 px-4 rounded-xl text-xs font-black border-destructive/40 text-destructive hover:bg-destructive/5"
              onClick={() => onReject(session.id)}
              disabled={rejectPending}
            >
              {rejectPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5 mr-1" />}
              Decline
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-9 px-3 rounded-xl text-xs font-black text-amber-700 border-amber-300 hover:bg-amber-50"
              onClick={() => onOpen(session)}
            >
              <MessageSquare className="w-3.5 h-3.5 mr-1" /> View
            </Button>
          </>
        )}
        {isActive && (
          <Button
            size="sm"
            className="h-9 px-4 rounded-xl text-xs font-black"
            onClick={() => onOpen(session)}
          >
            <MessageSquare className="w-3.5 h-3.5 mr-1" /> Open Chat
          </Button>
        )}
        {!isRequested && !isActive && (
          <button
            className="p-2 rounded-xl hover:bg-muted transition-colors"
            onClick={() => onOpen(session)}
            title="View history"
          >
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </button>
        )}
      </div>
    </div>
  );
}

export default function DoctorConsultations() {
  const [activeTab,    setActiveTab]    = useState('incoming'); // 'incoming' | 'active' | 'history'
  const [openSession,  setOpenSession]  = useState(null);

  const { data: consultations = [], isLoading } = useConsultations();
  const acceptMutation  = useAcceptConsultation();
  const rejectMutation  = useRejectConsultation();
  const endMutation     = useEndConsultation();

  const incoming  = consultations.filter((s) => s.status === 'REQUESTED');
  const active    = consultations.filter((s) => ['ACTIVE', 'ACCEPTED'].includes(s.status));
  const history   = consultations.filter((s) => ['COMPLETED', 'REJECTED'].includes(s.status));

  const handleAccept = async (sessionId) => {
    const updated = await acceptMutation.mutateAsync(sessionId);
    if (openSession?.id === sessionId) setOpenSession(updated);
  };

  const handleReject = (sessionId) => rejectMutation.mutate(sessionId);

  const handleEnd = (notes) => {
    if (!openSession) return;
    endMutation.mutate({ sessionId: openSession.id, notes }, {
      onSuccess: (updated) => {
        setOpenSession(updated);
      },
    });
  };

  const TABS = [
    { id: 'incoming', label: 'Incoming',  icon: Inbox,        count: incoming.length },
    { id: 'active',   label: 'Active',    icon: MessageSquare, count: active.length },
    { id: 'history',  label: 'History',   icon: History,       count: null },
  ];

  const currentList = activeTab === 'incoming' ? incoming : activeTab === 'active' ? active : history;

  return (
    <div className="flex flex-col gap-6 py-4">
      {/* Header */}
      <div>
        <h2 className="text-3xl md:text-4xl font-display font-extrabold text-foreground tracking-tight flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white shadow-xl shadow-primary/20">
            <Stethoscope className="w-6 h-6" />
          </div>
          Consultations
        </h2>
        <p className="text-muted-foreground font-medium mt-1">
          Manage patient consultation requests and real-time sessions.
        </p>
      </div>

      {/* Summary chips */}
      <div className="flex flex-wrap gap-3">
        {incoming.length > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-full">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            <span className="text-xs font-black text-amber-700">{incoming.length} awaiting response</span>
          </div>
        )}
        {active.length > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-full">
            <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />
            <span className="text-xs font-black text-emerald-700">{active.length} active chat{active.length > 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      <div className={`flex gap-6 ${openSession ? 'lg:flex-row' : ''}`}>
        {/* Left panel: list */}
        <div className={`flex flex-col gap-4 ${openSession ? 'w-full lg:w-96 flex-shrink-0' : 'w-full'}`}>
          {/* Tabs */}
          <div className="flex gap-2 p-1.5 bg-muted/40 rounded-2xl w-fit">
            {TABS.map(({ id, label, icon: Icon, count }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                  activeTab === id
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
                {count > 0 && (
                  <span className="w-5 h-5 bg-primary text-primary-foreground rounded-full text-[10px] font-black flex items-center justify-center">
                    {count}
                  </span>
                )}
              </button>
            ))}
          </div>

          <Card className="rounded-[2rem] overflow-hidden">
            <CardContent className="p-4 flex flex-col gap-3">
              {isLoading ? (
                <div className="flex items-center justify-center py-12 gap-3 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm">Loading…</span>
                </div>
              ) : currentList.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  {activeTab === 'incoming' && <Inbox className="w-10 h-10 text-muted-foreground/30 mb-3" />}
                  {activeTab === 'active'   && <MessageSquare className="w-10 h-10 text-muted-foreground/30 mb-3" />}
                  {activeTab === 'history'  && <History className="w-10 h-10 text-muted-foreground/30 mb-3" />}
                  <p className="font-bold text-foreground">
                    {activeTab === 'incoming' ? 'No pending requests' : activeTab === 'active' ? 'No active sessions' : 'No history yet'}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {activeTab === 'incoming' ? 'New requests from patients will appear here.' : ''}
                  </p>
                </div>
              ) : (
                currentList.map((session) => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    onOpen={setOpenSession}
                    onAccept={handleAccept}
                    onReject={handleReject}
                    acceptPending={acceptMutation.isPending}
                    rejectPending={rejectMutation.isPending}
                  />
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right panel: chat */}
        {openSession && (
          <div className="flex-1 min-w-0 h-[600px]">
            <DoctorChatRoom
              session={openSession}
              isDoctor={true}
              onEnd={handleEnd}
              onClose={() => setOpenSession(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
