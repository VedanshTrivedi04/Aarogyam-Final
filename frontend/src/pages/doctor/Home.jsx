import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate, Link } from 'react-router-dom';
import {
  Users, AlertCircle, Search, Pill,
  ChevronRight, Activity, ArrowUpRight, Filter,
  Stethoscope, Calendar, UserCircle, Loader2, Bot, Bell,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useDoctorPatients, useDoctorPatientsData } from '@/hooks/useDoctor';
import { useNotifications } from '@/hooks/useNotifications';

function timeAgo(dateString) {
  if (!dateString) return '';
  const diffMin = Math.floor((Date.now() - new Date(dateString).getTime()) / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

const AdherenceBar = ({ pct }) => {
  const safe = Number.isFinite(pct) ? pct : 0;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className={`text-xs font-black uppercase tracking-tighter ${safe >= 85 ? 'text-success' : safe >= 70 ? 'text-accent' : 'text-destructive'}`}>
          {safe}% Rate
        </span>
      </div>
      <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${safe}%` }}
          className={`h-full rounded-full ${safe >= 85 ? 'bg-success' : safe >= 70 ? 'bg-accent' : 'bg-destructive'}`}
        />
      </div>
    </div>
  );
};

const PatientRow = ({ patient, adherencePct, alertCount, onClick }) => (
  <tr
    className="hover:bg-muted/30 transition-colors cursor-pointer group"
    onClick={() => onClick(patient.id)}
  >
    <td className="px-6 py-5">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary font-display font-black text-xl shadow-inner">
          {(patient.name || '?')[0]}
        </div>
        <div>
          <h4 className="font-bold text-foreground text-lg">{patient.name}</h4>
          <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest">
            {patient.patientCode} • Linked {patient.linkedAt ? new Date(patient.linkedAt).toLocaleDateString() : '—'}
          </p>
        </div>
      </div>
    </td>
    <td className="px-6 py-5">
      <AdherenceBar pct={adherencePct} />
    </td>
    <td className="px-6 py-5 text-center">
      <Badge
        variant={adherencePct >= 70 ? 'success' : 'danger'}
        className="h-6 px-3 rounded-full text-[9px] font-black uppercase tracking-widest"
      >
        {adherencePct >= 85 ? 'stable' : adherencePct >= 70 ? 'watch' : 'at risk'}
      </Badge>
    </td>
    <td className="px-6 py-5 text-center">
      {alertCount > 0 && (
        <span className="inline-flex items-center justify-center w-6 h-6 bg-destructive/10 text-destructive text-xs font-black rounded-full">
          {alertCount}
        </span>
      )}
    </td>
    <td className="px-6 py-5 text-right">
      <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button variant="ghost" size="sm" className="h-10 w-10 p0 rounded-xl bg-secondary hover:bg-primary/10"><Pill className="w-5 h-5 text-primary" /></Button>
        <div className="w-10 h-10 flex items-center justify-center"><ChevronRight className="w-5 h-5 text-muted-foreground" /></div>
      </div>
    </td>
  </tr>
);

export default function DoctorHome() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const { data: patients = [], isLoading } = useDoctorPatients();
  const patientsData = useDoctorPatientsData(patients);
  const { data: aiAlertsData, isLoading: isAiAlertsLoading } = useNotifications({ type: 'DOCTOR_ALERT', page_size: 5 });
  const aiAlerts = aiAlertsData?.results || [];

  const enriched = useMemo(() => patients.map(p => {
    const d = patientsData[p.id] || {};
    const adherence = d.adherence;
    const pct = Math.round(
      adherence?.adherence_pct ?? adherence?.adherence_rate ?? adherence?.summary?.adherence_pct ?? 0
    );
    const alerts = Array.isArray(d.alerts) ? d.alerts : [];
    return { ...p, adherencePct: pct, alertCount: alerts.length };
  }), [patients, patientsData]);

  const filtered = useMemo(() => {
    if (!search.trim()) return enriched;
    const q = search.toLowerCase();
    return enriched.filter(p => p.name.toLowerCase().includes(q) || p.patientCode.toLowerCase().includes(q));
  }, [enriched, search]);

  const atRiskCount  = enriched.filter(p => p.adherencePct < 70).length;
  const avgAdherence = enriched.length
    ? Math.round(enriched.reduce((s, p) => s + p.adherencePct, 0) / enriched.length)
    : 0;

  return (
    <div className="flex flex-col gap-8 py-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h2 className="text-3xl md:text-4xl font-display font-extrabold text-foreground tracking-tight flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white shadow-xl shadow-primary/20">
              <Stethoscope className="w-6 h-6" />
            </div>
            Clinical Overview
          </h2>
          <p className="text-muted-foreground font-medium mt-1">
            Monitoring {isLoading ? '…' : enriched.length} patients under your care.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" className="h-12 px-6 rounded-xl border-border/60 font-bold bg-card shadow-sm">
            <Filter className="w-4 h-4 mr-2" /> Filter Registry
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 flex flex-col gap-8">
          {/* Quick Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <Card className="rounded-3xl border-border/50">
              <CardContent className="p-6">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-4">Total Registry</p>
                <div className="flex items-center justify-between">
                  <h3 className="text-4xl font-display font-black tracking-tight">
                    {isLoading ? <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /> : enriched.length}
                  </h3>
                  <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
                    <Users className="w-6 h-6" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="rounded-3xl border-border/50">
              <CardContent className="p-6">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-4">Avg. Adherence</p>
                <div className="flex items-center justify-between">
                  <h3 className={`text-4xl font-display font-black tracking-tight ${avgAdherence >= 70 ? 'text-success' : 'text-destructive'}`}>
                    {avgAdherence}%
                  </h3>
                  <div className="w-12 h-12 rounded-2xl bg-success/10 flex items-center justify-center text-success">
                    <Activity className="w-6 h-6" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-destructive/5 border-destructive/20 rounded-3xl">
              <CardContent className="p-6">
                <p className="text-[10px] font-black uppercase tracking-widest text-destructive mb-4">High Risk Flags</p>
                <div className="flex items-center justify-between">
                  <h3 className="text-4xl font-display font-black tracking-tight text-destructive">{atRiskCount}</h3>
                  <div className="w-12 h-12 rounded-2xl bg-destructive/10 flex items-center justify-center text-destructive">
                    <AlertCircle className="w-6 h-6" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Patient List */}
          <Card className="rounded-[2.5rem] overflow-hidden">
            <CardHeader className="flex flex-col md:flex-row items-center justify-between gap-4 p-8 bg-muted/10 border-b border-border/40">
              <h3 className="text-2xl font-display font-bold tracking-tight">Patient Registry</h3>
              <div className="relative w-full md:w-72">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  placeholder="Search by name or code..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 bg-card border border-border/60 rounded-2xl outline-none text-sm font-medium focus:border-primary/50 transition-all"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {isLoading ? (
                <div className="flex items-center justify-center p-16 text-muted-foreground gap-3">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm font-medium">Loading patients…</span>
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-16 text-center">
                  <Users className="w-10 h-10 text-muted-foreground/30 mb-3" />
                  <p className="font-bold text-foreground">{search ? 'No results found' : 'No linked patients'}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {search ? 'Try a different search term.' : 'Patients will appear here once they link you as their doctor.'}
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-muted/30 text-muted-foreground uppercase text-[10px] font-black tracking-[0.2em] border-b border-border/40">
                      <tr>
                        <th className="px-6 py-5 text-left font-black">Patient Details</th>
                        <th className="px-6 py-5 text-left font-black">Weekly Adherence</th>
                        <th className="px-6 py-5 text-center font-black">Status</th>
                        <th className="px-6 py-5 text-center font-black">Alerts</th>
                        <th className="px-6 py-5 text-right font-black">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {filtered.map(p => (
                        <PatientRow
                          key={p.id}
                          patient={p}
                          adherencePct={p.adherencePct}
                          alertCount={p.alertCount}
                          onClick={(id) => navigate(`/doctor/patient/${id}`)}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Side Panel */}
        <div className="flex flex-col gap-8">
          {/* AI Agent Alerts — patients the Agentic AI flagged for doctor review */}
          <Card className="rounded-[2.5rem] overflow-hidden border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-transparent">
            <CardHeader className="p-8 pb-0">
              <h3 className="text-xl font-display font-bold text-foreground flex items-center gap-3">
                <Bot className="w-6 h-6 text-primary" /> AI Agent Alerts
              </h3>
              <p className="text-xs text-muted-foreground mt-1">Patients the AI Agent flagged for your review</p>
            </CardHeader>
            <CardContent className="p-8 flex flex-col gap-4">
              {isAiAlertsLoading ? (
                <div className="flex items-center justify-center py-6 text-muted-foreground gap-3">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-xs font-medium">Loading…</span>
                </div>
              ) : aiAlerts.length === 0 ? (
                <p className="text-sm text-muted-foreground font-medium text-center py-4">
                  No AI-flagged patients right now.
                </p>
              ) : (
                aiAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="p-4 bg-card rounded-2xl border border-border/50 flex items-start gap-3 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => alert.data?.deep_link && navigate(alert.data.deep_link)}
                  >
                    <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
                      <Bell className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h5 className="font-bold text-foreground text-sm truncate">{alert.title}</h5>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{alert.body}</p>
                      <p className="text-[10px] text-muted-foreground/70 font-black uppercase tracking-widest mt-1.5">
                        {timeAgo(alert.created_at)}
                      </p>
                    </div>
                  </div>
                ))
              )}
              <Link to="/notifications">
                <Button variant="ghost" className="w-full h-11 text-primary font-black uppercase tracking-widest text-[10px] hover:bg-primary/10">
                  View All Alerts
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Critical Flags */}
          <Card className="border-destructive/30 bg-destructive/5 rounded-[2.5rem] overflow-hidden shadow-2xl shadow-destructive/5">
            <CardHeader className="p-8 pb-0">
              <h3 className="text-xl font-display font-bold text-destructive flex items-center gap-3">
                <AlertCircle className="w-6 h-6" /> Critical Flags
              </h3>
            </CardHeader>
            <CardContent className="p-8 flex flex-col gap-4">
              {enriched.filter(p => p.adherencePct < 70).slice(0, 3).map(p => (
                <div
                  key={p.id}
                  className="p-5 bg-white rounded-3xl border border-destructive/10 flex flex-col gap-3 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => navigate(`/doctor/patient/${p.id}`)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h5 className="font-bold text-foreground text-lg">{p.name}</h5>
                      <p className="text-[10px] text-destructive font-black uppercase tracking-widest">{p.adherencePct}% adherence</p>
                    </div>
                    <Badge variant="danger" className="text-[9px] h-5 px-2 rounded-full">CRITICAL</Badge>
                  </div>
                  <Button variant="danger" size="sm" className="w-full h-10 text-[10px] font-black uppercase tracking-widest rounded-xl">
                    Intervene Now
                  </Button>
                </div>
              ))}
              {enriched.filter(p => p.adherencePct < 70).length === 0 && !isLoading && (
                <p className="text-sm text-muted-foreground font-medium text-center py-4">No critical flags — all patients stable.</p>
              )}
              <Link to="/doctor/critical">
                <Button variant="ghost" className="w-full h-12 text-destructive font-black uppercase tracking-widest text-[10px] hover:bg-destructive/10">
                  View All Critical Flags
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Recent Consultations placeholder */}
          <Card className="rounded-[2.5rem] overflow-hidden border-border/40">
            <CardHeader className="p-8 pb-0">
              <h3 className="text-xl font-display font-bold text-foreground flex items-center gap-3">
                <Calendar className="w-6 h-6 text-primary" /> Quick Actions
              </h3>
            </CardHeader>
            <CardContent className="p-8 flex flex-col gap-5">
              {[
                { label: 'Consultations & Live Chat', to: '/doctor/consultations' },
                { label: 'View All Prescriptions', to: '/doctor/prescribe/0' },
                { label: 'Critical Adherence Flags', to: '/doctor/critical' },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-4 group cursor-pointer" onClick={() => navigate(item.to)}>
                  <div className="w-12 h-12 rounded-2xl bg-secondary flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all shadow-sm">
                    <UserCircle className="w-7 h-7" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h5 className="font-bold text-foreground truncate">{item.label}</h5>
                  </div>
                  <ArrowUpRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <footer className="mt-8 pt-8 border-t border-border/40 flex items-center justify-between text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground opacity-50">
        <span>MedAdhere Clinical Suite</span>
        <div className="flex gap-6">
          <span>GDPR Compliant</span>
          <span>End-to-End Encryption</span>
        </div>
      </footer>
    </div>
  );
}
