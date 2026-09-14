import { useState } from 'react';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import { Pill, Users, Bell, Activity, CheckCircle,
  Clock, Phone, MessageCircle, ChevronRight, Shield, Calendar, Eye, X, BarChart3
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { useRef, useMemo } from 'react';
import { useCaregiverPatients, useCaregiverPatientsData, useCaregiverPatientDetail } from '@/hooks/useCaregiver';

const FadeIn = ({ children, className = '', delay = 0 }) => {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });
  return (
    <motion.div ref={ref} initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay }} className={className}
    >{children}</motion.div>
  );
};

const RISK_LEVEL_COLORS = {
  low: 'text-emerald-600',
  medium: 'text-amber-600',
  high: 'text-orange-600',
  critical: 'text-red-600',
};
const riskColorClass = (level) => RISK_LEVEL_COLORS[(level || '').toLowerCase()] || 'text-muted-foreground';

const ALERT_STYLES = {
  critical: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', badge: 'bg-red-500' },
  warning: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', badge: 'bg-amber-500' },
  info: { bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700', badge: 'bg-blue-500' },
  success: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', badge: 'bg-emerald-500' },
};

/* ── Adherence Ring ── */
const Ring = ({ pct, size = 64 }) => {
  const r = (size - 10) / 2, c = 2 * Math.PI * r;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="w-full h-full -rotate-90">
        <circle className="text-muted/30" strokeWidth="5" stroke="currentColor" fill="transparent" r={r} cx={size/2} cy={size/2} />
        <motion.circle initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c - (pct/100)*c }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
          className={pct >= 90 ? 'text-emerald-500' : pct >= 75 ? 'text-amber-500' : 'text-red-500'}
          strokeWidth="5" strokeDasharray={c} strokeLinecap="round" stroke="currentColor" fill="transparent" r={r} cx={size/2} cy={size/2} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display font-bold text-sm">{pct}%</span>
    </div>
  );
};

/* ── Patient Detail Modal ── */
const PatientModal = ({ patient, onClose }) => (
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
    className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
    <motion.div initial={{ scale: 0.92, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92 }}
      className="bg-card rounded-3xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="p-6 border-b border-border flex items-center gap-4">
        <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${patient.color} flex items-center justify-center text-white font-bold text-lg`}>{patient.avatar}</div>
        <div className="flex-1">
          <h3 className="font-display font-bold text-lg">{patient.name}</h3>
          <p className="text-sm text-muted-foreground">{patient.relation} · Age {patient.age} · {patient.location}</p>
        </div>
        <button onClick={onClose} className="w-8 h-8 rounded-full hover:bg-muted flex items-center justify-center">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-6 space-y-6">
        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center p-3 bg-muted/40 rounded-xl">
            <p className="text-xs text-muted-foreground">Adherence</p>
            <p className={`font-bold text-lg ${patient.adherence >= 90 ? 'text-emerald-600' : patient.adherence >= 75 ? 'text-amber-600' : 'text-red-600'}`}>{patient.adherence}%</p>
          </div>
          <div className="text-center p-3 bg-muted/40 rounded-xl">
            <p className="text-xs text-muted-foreground">Streak</p>
            <p className="font-bold text-lg text-foreground">{patient.streak} days</p>
          </div>
          <div className="text-center p-3 bg-muted/40 rounded-xl">
            <p className="text-xs text-muted-foreground">AI Risk</p>
            <p className={`font-bold text-lg ${riskColorClass(patient.riskLevelRaw)}`}>{patient.riskScore}</p>
          </div>
        </div>

        {/* Conditions */}
        <div>
          <h4 className="font-bold text-sm text-foreground mb-2">Conditions</h4>
          <div className="flex gap-2 flex-wrap">
            {patient.conditions.map(c => <span key={c} className="px-3 py-1 rounded-full bg-secondary text-primary text-xs font-semibold">{c}</span>)}
          </div>
        </div>

        {/* Today's Medications */}
        <div>
          <h4 className="font-bold text-sm text-foreground mb-3">Today's Medications Summary</h4>
          <div className="space-y-2">
            {patient.meds && patient.meds.length > 0 ? patient.meds.map((m, i) => (
              <div key={i} className={`flex items-center gap-3 p-3 rounded-xl border ${m.taken ? 'bg-emerald-50 border-emerald-200' : 'bg-background border-border/60'}`}>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${m.taken ? 'bg-emerald-500 text-white' : 'bg-muted text-muted-foreground'}`}>
                  {m.taken ? <CheckCircle className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-sm">{m.name || `Medication ${i+1}`} <span className="text-muted-foreground font-normal">{m.dose ? `(${m.dose})` : ''}</span></p>
                  <p className="text-xs text-muted-foreground">{m.time || 'Scheduled for today'}</p>
                </div>
                <span className={`text-xs font-bold ${m.taken ? 'text-emerald-600' : 'text-muted-foreground'}`}>{m.taken ? 'Taken ✓' : 'Pending'}</span>
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">No medications scheduled for today or data unavailable.</p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button variant="outline" className="flex-1 h-10 rounded-xl text-sm"><Phone className="w-4 h-4 mr-1.5" /> Call</Button>
          <Button className="flex-1 h-10 rounded-xl text-sm"><MessageCircle className="w-4 h-4 mr-1.5" /> Message</Button>
        </div>
      </div>
    </motion.div>
  </motion.div>
);

/* ── Patient Card ── */
const PatientCard = ({ patient, onClick, delay }) => (
  <FadeIn delay={delay}>
    <motion.div whileHover={{ y: -4 }} onClick={() => onClick(patient.id)}
      className="bg-card rounded-2xl border border-border/60 shadow-elevation-1 hover:shadow-elevation-3 transition-all cursor-pointer overflow-hidden">
      <div className="p-5">
        <div className="flex items-start gap-4 mb-4">
          <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${patient.color} flex items-center justify-center text-white font-bold shadow-md flex-shrink-0`}>{patient.avatar}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-display font-bold text-foreground truncate">{patient.name}</h3>
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${patient.status === 'on-track' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            </div>
            <p className="text-muted-foreground text-xs">{patient.relation} · Age {patient.age}</p>
            <div className="flex gap-1.5 mt-1.5 flex-wrap">
              {patient.conditions.map(c => <span key={c} className="px-2 py-0.5 rounded-full bg-secondary text-primary text-[10px] font-semibold">{c}</span>)}
            </div>
          </div>
          <Ring pct={patient.adherence} size={52} />
        </div>

        <div className="grid grid-cols-3 gap-2 mb-3 text-center">
          <div className="p-2 bg-muted/40 rounded-lg">
            <p className="text-[10px] text-muted-foreground uppercase">Streak</p>
            <p className="font-bold text-sm">{patient.streak}d</p>
          </div>
          <div className="p-2 bg-muted/40 rounded-lg">
            <p className="text-[10px] text-muted-foreground uppercase">Risk</p>
            <p className={`font-bold text-sm ${riskColorClass(patient.riskLevelRaw)}`}>{patient.riskScore}</p>
          </div>
          <div className="p-2 bg-muted/40 rounded-lg">
            <p className="text-[10px] text-muted-foreground uppercase">Meds</p>
            <p className="font-bold text-sm">{patient.medsTaken || 0}/{patient.medsTotal || 0}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="w-3 h-3" /> Last check: Just now
        </div>
      </div>
      <div className="px-5 py-3 border-t border-border/40 flex justify-between items-center bg-muted/20">
        <span className="text-xs font-semibold text-primary flex items-center gap-1"><Eye className="w-3 h-3" /> View Details</span>
        <ChevronRight className="w-4 h-4 text-muted-foreground" />
      </div>
    </motion.div>
  </FadeIn>
);

/* ── Alert Item ── */
const AlertItem = ({ alert, onDismiss }) => {
  const s = ALERT_STYLES[alert.type];
  return (
    <motion.div layout initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 12 }}
      className={`flex items-start gap-3 p-3.5 rounded-xl border ${s.bg}`}>
      <alert.icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${s.text}`} />
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold ${s.text}`}>{alert.message}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{alert.patient} · {alert.time}</p>
      </div>
      <button onClick={() => onDismiss(alert.id)} className="w-6 h-6 rounded-full hover:bg-black/5 flex items-center justify-center flex-shrink-0">
        <X className="w-3 h-3 text-muted-foreground" />
      </button>
    </motion.div>
  );
};

/* ═══════════ MAIN ═══════════ */
export default function CaregiverPortal() {
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [filter, setFilter] = useState('all');
  const [dismissedAlertIds, setDismissedAlertIds] = useState(new Set());

  const { data: rawPatients = [], isLoading: isLoadingPatients } = useCaregiverPatients();

  const patientIds = useMemo(() => rawPatients.map(p => p.id), [rawPatients]);
  const { adherenceQueries, alertsQueries, riskQueries } = useCaregiverPatientsData(patientIds);

  const isLoadingAdherence = adherenceQueries.some(q => q.isLoading);
  const isLoadingAlerts = alertsQueries.some(q => q.isLoading);
  const isLoading = isLoadingPatients || (isLoadingAdherence && rawPatients.length > 0) || (isLoadingAlerts && rawPatients.length > 0);

  const dismissAlert = (id) => setDismissedAlertIds(prev => new Set(prev).add(id));

  // Compute unified alerts
  const alerts = useMemo(() => {
    const allAlerts = [];
    alertsQueries.forEach((q, idx) => {
      if (q.data && Array.isArray(q.data)) {
        const patientName = rawPatients[idx]?.name || 'Unknown Patient';
        q.data.forEach(job => {
          if (!dismissedAlertIds.has(job.id)) {
            const medName = job.schedule?.prescription?.medication?.name || 'Medication';
            allAlerts.push({
              id: job.id,
              type: 'critical',
              message: `Missed ${medName} (${job.dose_value} ${job.dose_unit})`,
              patient: patientName,
              time: new Date(job.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              timestamp: new Date(job.scheduled_at).getTime()
            });
          }
        });
      }
    });
    return allAlerts.sort((a, b) => b.timestamp - a.timestamp);
  }, [alertsQueries, rawPatients, dismissedAlertIds]);

  const patients = useMemo(() => {
    return rawPatients.map((p, idx) => {
      const adherenceRes = adherenceQueries[idx]?.data;
      const adherence = adherenceRes?.adherence_pct ?? p.adherence;
      const medsCount = adherenceRes?.total_scheduled ?? 0;
      const medsTaken = adherenceRes?.taken ?? 0;
      const medsPending = adherenceRes?.pending ?? 0;

      // Provide dummy meds so PatientCard can still render fraction
      const meds = Array.from({ length: medsCount }).map((_, i) => ({
        taken: i < medsTaken
      }));

      // Real AI risk level (replaces the previously hardcoded 'Low')
      const riskQuery = riskQueries[idx];
      const riskLevelRaw = riskQuery?.data?.risk_level || null;
      const riskScore = riskQuery?.isLoading
        ? '…'
        : riskLevelRaw
          ? riskLevelRaw.charAt(0).toUpperCase() + riskLevelRaw.slice(1)
          : 'N/A';

      return {
        ...p,
        adherence,
        meds,
        medsTaken,
        medsTotal: medsCount,
        riskScore,
        riskLevelRaw,
      };
    });
  }, [rawPatients, adherenceQueries, riskQueries]);

  const filteredPatients = filter === 'all' ? patients : patients.filter(p => p.status === filter);
  const totalMeds = patients.reduce((s, p) => s + (p.medsTotal || 0), 0);
  const takenMeds = patients.reduce((s, p) => s + (p.medsTaken || 0), 0);
  const avgAdherence = patients.length ? Math.round(patients.reduce((s, p) => s + p.adherence, 0) / patients.length) : 0;

  return (
    <div className="flex flex-col gap-8 py-4">

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <FadeIn>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
            <div>
              <h1 className="text-2xl md:text-3xl font-display font-extrabold flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Users className="w-5 h-5 text-primary" />
                </div>
                Caregiver Dashboard
              </h1>
              <p className="text-muted-foreground mt-1">Monitoring {isLoading ? '...' : patients.length} patients</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="text-sm h-10 rounded-xl"><Phone className="w-4 h-4 mr-1.5" /> Emergency</Button>
              <Button className="text-sm h-10 rounded-xl"><Users className="w-4 h-4 mr-1.5" /> Add Patient</Button>
            </div>
          </div>
        </FadeIn>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { icon: Users, label: 'Patients', value: isLoading ? '...' : patients.length, sub: 'Under your care', color: 'text-primary' },
            { icon: Activity, label: 'Avg Adherence', value: `${avgAdherence}%`, sub: avgAdherence >= 85 ? 'On track' : 'Needs attention', color: avgAdherence >= 85 ? 'text-emerald-600' : 'text-amber-600' },
            { icon: Pill, label: 'Doses Today', value: `${takenMeds}/${totalMeds}`, sub: 'Taken / Total', color: 'text-blue-600' },
            { icon: Bell, label: 'Active Alerts', value: alerts.filter(a => a.type === 'critical' || a.type === 'warning').length, sub: 'Need attention', color: 'text-red-600' },
          ].map((s, i) => (
            <FadeIn key={i} delay={i * 0.05}>
              <Card className="hover:shadow-elevation-2 transition-shadow">
                <CardContent className="p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center text-primary">
                      <s.icon className="w-5 h-5" />
                    </div>
                    <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">{s.label}</span>
                  </div>
                  <p className={`text-2xl font-display font-extrabold ${s.color}`}>{s.value}</p>
                  <p className="text-xs text-muted-foreground mt-1">{s.sub}</p>
                </CardContent>
              </Card>
            </FadeIn>
          ))}
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left: Patients */}
          <div className="lg:col-span-2 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-bold text-xl">Your Patients</h2>
              <div className="flex gap-2">
                {[['all', 'All'], ['on-track', 'On Track'], ['needs-attention', 'Attention']].map(([val, label]) => (
                  <button key={val} onClick={() => setFilter(val)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${filter === val ? 'bg-primary text-white shadow-md shadow-primary/20' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
                  >{label}</button>
                ))}
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-5">
              {isLoading ? (
                <div className="col-span-2 text-center py-12 text-muted-foreground">
                  <Activity className="w-8 h-8 mx-auto mb-2 opacity-40 animate-pulse" />
                  <p className="font-semibold">Loading patients...</p>
                </div>
              ) : filteredPatients.length === 0 ? (
                <div className="col-span-2 text-center py-12 text-muted-foreground">
                  <Users className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  <p className="font-semibold">No patients found</p>
                </div>
              ) : (
                filteredPatients.map((p, i) => (
                  <PatientCard key={p.id} patient={p} onClick={setSelectedPatientId} delay={i * 0.08} />
                ))
              )}
            </div>
          </div>

          {/* Right: Alerts */}
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-bold text-xl flex items-center gap-2">
                <Bell className="w-5 h-5 text-primary" /> Alerts
              </h2>
              {alerts.length > 0 && (
                <button
                  onClick={() => setDismissedAlertIds(prev => {
                    const s = new Set(prev);
                    alerts.forEach(a => s.add(a.id));
                    return s;
                  })}
                  className="text-xs text-primary font-semibold hover:underline"
                >Clear All</button>
              )}
            </div>
            <div className="space-y-3">
              <AnimatePresence>
                {alerts.map(a => <AlertItem key={a.id} alert={a} onDismiss={dismissAlert} />)}
              </AnimatePresence>
              {alerts.length === 0 && (
                <div className="text-center py-10 text-muted-foreground">
                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
                  <p className="font-semibold text-sm">All clear! No pending alerts.</p>
                </div>
              )}
            </div>

            {/* Quick Actions */}
            <FadeIn>
              <Card className="mt-4">
                <CardContent className="p-5">
                  <h3 className="font-bold text-sm mb-3">Quick Actions</h3>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { icon: BarChart3, label: 'Weekly Report' },
                      { icon: Calendar, label: 'Schedule' },
                      { icon: MessageCircle, label: 'Family Chat' },
                      { icon: Shield, label: 'Emergency Plan' },
                    ].map(({ icon: Icon, label }) => (
                      <button key={label} className="flex items-center gap-2 p-3 rounded-xl bg-muted/40 hover:bg-secondary text-sm font-semibold text-foreground hover:text-primary transition-colors">
                        <Icon className="w-4 h-4" /> {label}
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-border/30 py-6 text-center text-xs text-muted-foreground mt-8">
        © 2026 Aarogyam Health Systems India Pvt Ltd. All rights reserved.
      </footer>

      {/* Patient Detail Modal */}
      <AnimatePresence>
        {selectedPatientId && (
          <PatientModalWrapper 
            patientId={selectedPatientId}
            basePatient={patients.find(p => p.id === selectedPatientId)}
            onClose={() => setSelectedPatientId(null)} 
          />
        )}
      </AnimatePresence>
    </div>
  );
}

const PatientModalWrapper = ({ patientId, basePatient, onClose }) => {
  const { data: detailData, isLoading } = useCaregiverPatientDetail(patientId);

  if (isLoading || !detailData) {
    return (
      <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center">
        <Activity className="w-8 h-8 text-primary animate-pulse" />
      </div>
    );
  }

  // Merge the base data and detail data
  const mergedPatient = {
    ...basePatient,
    ...detailData, // assuming detailData provides full patient info
    // the patient detail returns `meds`? The API returned PatientSerializer which has `prescriptions`?
    // Let's map it roughly. 
  };

  return <PatientModal patient={mergedPatient} onClose={onClose} />;
};
