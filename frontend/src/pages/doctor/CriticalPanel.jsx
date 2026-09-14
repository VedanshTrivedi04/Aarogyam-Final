import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ArrowLeft, TrendingDown, TrendingUp, ShieldAlert,
  Clock, Heart, Loader2, Brain,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useDoctorPatients, useDoctorPatientsData } from '@/hooks/useDoctor';

const riskLevel = (pct) => {
  if (pct < 50) return { label: 'Extreme', color: 'from-red-500 to-rose-600' };
  if (pct < 65) return { label: 'High', color: 'from-orange-500 to-amber-600' };
  return { label: 'Moderate', color: 'from-yellow-500 to-orange-400' };
};

const AI_RISK_LEVEL_COLORS = {
  low: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  medium: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  high: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
  critical: 'bg-destructive/10 text-destructive border-destructive/20',
};

const FlagCard = ({ patient, adherencePct, missedCount, recentAlert, aiRisk, onAction }) => {
  const risk = riskLevel(adherencePct);
  const aiRiskColor = AI_RISK_LEVEL_COLORS[(aiRisk?.risk_level || '').toLowerCase()] || 'bg-muted text-muted-foreground border-border';
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-card rounded-[2.5rem] border border-destructive/20 shadow-elevation-3 overflow-hidden group hover:shadow-destructive/10 transition-all"
    >
      <div className="p-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
          <div className="flex items-center gap-5">
            <div className={`w-16 h-16 rounded-[1.5rem] bg-gradient-to-br ${risk.color} flex items-center justify-center text-white font-display font-black text-2xl shadow-lg`}>
              {patient.name[0]}
            </div>
            <div>
              <h3 className="text-2xl font-display font-extrabold text-foreground tracking-tight">{patient.name}</h3>
              <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                {patient.patientCode} • {patient.linkedAt ? new Date(patient.linkedAt).toLocaleDateString() : '—'}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <Badge variant="danger" className="h-7 px-4 rounded-full text-[10px] font-black uppercase tracking-widest shadow-lg shadow-destructive/20">
              {risk.label} Risk
            </Badge>
            {aiRisk?.risk_level && (
              <span className={`inline-flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full border ${aiRiskColor}`}>
                <Brain className="w-3 h-3" />
                AI: {aiRisk.risk_level}
                {typeof aiRisk.risk_score === 'number' && ` · ${Math.round(aiRisk.risk_score * 100)}%`}
                {aiRisk.risk_trend === 'improving' && <TrendingUp className="w-3 h-3" />}
                {aiRisk.risk_trend === 'worsening' && <TrendingDown className="w-3 h-3" />}
              </span>
            )}
            {recentAlert && (
              <span className="text-[10px] font-black text-destructive uppercase tracking-widest mt-1 flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> {new Date(recentAlert.scheduled_at).toLocaleString()}
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="p-6 bg-destructive/5 rounded-[2rem] border border-destructive/10">
            <p className="text-[10px] font-black uppercase tracking-widest text-destructive/70 mb-2">30-Day Adherence</p>
            <p className="text-4xl font-display font-black text-destructive">{adherencePct}%</p>
            <div className="flex items-center gap-1 text-xs text-destructive/60 font-bold mt-1">
              <TrendingDown className="w-3.5 h-3.5" /> Below threshold
            </div>
          </div>
          <div className="p-6 bg-muted/40 rounded-[2rem] border border-border/40">
            <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-2">Missed Doses</p>
            <p className="text-4xl font-display font-black text-foreground">{missedCount}</p>
            <p className="text-xs text-muted-foreground font-bold mt-1">Last 30 days</p>
          </div>
          <div className="p-6 bg-primary/5 rounded-[2rem] border border-primary/10">
            <p className="text-[10px] font-black uppercase tracking-widest text-primary mb-2">Patient Code</p>
            <p className="text-xl font-bold text-foreground truncate">{patient.patientCode || '—'}</p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <Button
            onClick={() => onAction(patient.id)}
            className="flex-1 h-14 rounded-2xl bg-destructive hover:bg-destructive/90 shadow-xl shadow-destructive/20 font-black uppercase tracking-widest text-xs"
          >
            View Clinical Profile
          </Button>
          <Button
            variant="outline"
            onClick={() => onAction(patient.id)}
            className="flex-1 h-14 rounded-2xl border-border/60 font-black uppercase tracking-widest text-xs"
          >
            New Prescription
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

export default function CriticalPanel() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const { data: patients = [], isLoading } = useDoctorPatients();
  const patientsData = useDoctorPatientsData(patients);

  const criticalFlags = useMemo(() => patients
    .map(p => {
      const d = patientsData[p.id] || {};
      const adherence = d.adherence;
      const pct = Math.round(
        adherence?.adherence_pct ?? adherence?.adherence_rate ?? adherence?.summary?.adherence_pct ?? 0
      );
      const alerts = Array.isArray(d.alerts) ? d.alerts : [];
      const missed = adherence?.missed ?? alerts.length;
      return { patient: p, adherencePct: pct, missedCount: missed, recentAlert: alerts[0] || null, aiRisk: d.risk };
    })
    .filter(f => f.adherencePct < 70)
    .sort((a, b) => a.adherencePct - b.adherencePct),
  [patients, patientsData]);

  const filtered = useMemo(() => {
    let list = criticalFlags;
    if (filter !== 'all') {
      list = list.filter(f => riskLevel(f.adherencePct).label.toLowerCase() === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(f => f.patient.name.toLowerCase().includes(q));
    }
    return list;
  }, [criticalFlags, filter, search]);

  return (
    <div className="flex flex-col gap-8 py-4 max-w-5xl mx-auto">
      <div className="flex flex-col gap-1">
        <button onClick={() => navigate('/doctor/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-2 w-fit">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em]">Clinical Registry</span>
        </button>
        <h2 className="text-4xl font-display font-extrabold text-foreground tracking-tight flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-destructive/10 flex items-center justify-center">
            <ShieldAlert className="w-7 h-7 text-destructive" />
          </div>
          High Priority Flags
        </h2>
        <p className="text-muted-foreground font-medium text-lg">
          {isLoading ? 'Loading…' : `${criticalFlags.length} patient${criticalFlags.length !== 1 ? 's' : ''} require immediate clinical attention.`}
        </p>
      </div>

      <Card className="bg-background border-border/40 p-2 rounded-[2rem]">
        <div className="flex flex-col md:flex-row gap-4 p-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground w-5 h-4" />
            <input
              placeholder="Filter by name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-card border border-border/50 rounded-2xl outline-none focus:ring-2 focus:ring-primary/20 transition-all font-sans font-medium"
            />
          </div>
          <div className="flex gap-2">
            {['all', 'extreme', 'high', 'moderate'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border
                  ${filter === f ? 'bg-primary text-white border-primary shadow-lg shadow-primary/20' : 'bg-card border-border hover:border-primary/50 text-muted-foreground'}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {isLoading ? (
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading clinical data…</span>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <AnimatePresence mode="popLayout">
            {filtered.map(({ patient, adherencePct, missedCount, recentAlert, aiRisk }) => (
              <FlagCard
                key={patient.id}
                patient={patient}
                adherencePct={adherencePct}
                missedCount={missedCount}
                recentAlert={recentAlert}
                aiRisk={aiRisk}
                onAction={(id) => navigate(`/doctor/patient/${id}`)}
              />
            ))}
          </AnimatePresence>

          {filtered.length === 0 && (
            <div className="text-center py-24 bg-muted/20 rounded-[3rem] border border-dashed border-border/60">
              <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm">
                <Heart className="w-8 h-8 text-success opacity-40" />
              </div>
              <h3 className="text-xl font-display font-bold text-foreground">
                {patients.length === 0 ? 'No linked patients' : 'No critical flags'}
              </h3>
              <p className="text-sm text-muted-foreground mt-1 font-medium">
                {patients.length === 0
                  ? 'Link patients to start monitoring adherence.'
                  : 'All patients are within clinical adherence thresholds.'}
              </p>
            </div>
          )}
        </div>
      )}

      <footer className="mt-8 flex items-center justify-center gap-6 opacity-40">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-destructive animate-pulse" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em]">Live clinical stream</span>
        </div>
      </footer>
    </div>
  );
}
