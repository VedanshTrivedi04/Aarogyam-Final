import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Clock, Activity, TrendingUp, AlertTriangle, Phone, MessageCircle,
  Calendar, MapPin, ShieldAlert, Heart, Pill, Stethoscope, CheckCircle2, XCircle,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useQuery } from '@tanstack/react-query';
import { useCaregiverPatients, useCaregiverPatientDetail, useCaregiverPatientAdherence, useCaregiverPatientAlerts, useUpdateCaregiverPatient } from '@/hooks/useCaregiver';
import { useRiskScore, useInsights, useRecommendations, useAgentActivity } from '@/hooks/useAi';
import { RiskMeter, AIInsightsCard, AgentActivityCard } from '@/components/ai';
import { axiosInstance } from '@/lib/axios';
import Reports from '../patient/Reports';
import ChatDrawer from '@/components/communications/ChatDrawer';
import CallModal from '@/components/communications/CallModal';

const StatCard = ({ label, value, icon: Icon, color = 'text-primary' }) => (
  <Card className="rounded-3xl border-border/50">
    <CardContent className="p-5">
      <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-3">{label}</p>
      <div className="flex items-center justify-between">
        <h3 className={`text-2xl font-display font-black ${color}`}>{value}</h3>
        <Icon className={`w-5 h-5 ${color} opacity-40`} />
      </div>
    </CardContent>
  </Card>
);

export default function PatientDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: patientList = [] } = useCaregiverPatients();
  const { data: patientDetail, isLoading: isDetailLoading } = useCaregiverPatientDetail(id);
  const { data: adherence } = useCaregiverPatientAdherence(id);
  const { data: alerts = [] } = useCaregiverPatientAlerts(id);
  const updateMutation = useUpdateCaregiverPatient();
  const { data: riskData, isLoading: isRiskLoading } = useRiskScore(id);
  const { data: insightsData, isLoading: isInsightsLoading } = useInsights(id);
  const { data: recommendationsData, isLoading: isRecsLoading } = useRecommendations(id);
  const { data: agentActivityData, isLoading: isAgentActivityLoading } = useAgentActivity(id);

  const [showChat, setShowChat] = useState(false);
  const [showCall, setShowCall] = useState(false);

  const { data: doctorPrescriptions = [], isLoading: loadingRx } = useQuery({
    queryKey: ['caregiver-doctor-rx', id],
    queryFn: async () => {
      const res = await axiosInstance.get(`/doctor/prescriptions/?patient=${id}`);
      return res.data?.data || [];
    },
    enabled: !!id,
  });

  const handleToggleTravelMode = () => {
    updateMutation.mutate({
      patientId: id,
      payload: { is_travel_mode: !patientDetail?.is_travel_mode }
    });
  };

  const patient = useMemo(() => {
    const listEntry = patientList.find((item) => String(item.id) === String(id));
    const detail = patientDetail || {};
    return {
      id,
      name: detail.full_name || listEntry?.name || 'Patient',
      patientCode: detail.patient_code || listEntry?.patientCode || '--',
      email: detail.email || listEntry?.email || '--',
      timezone: detail.timezone || listEntry?.timezone || 'Unknown',
      relation: 'Linked patient',
      activeMedsCount: listEntry?.activeMedsCount || 0,
      permission: listEntry?.permission || 'view_only',
      isHospitalized: detail.is_hospitalized,
      hospitalName: detail.hospital_name,
      isTravelMode: detail.is_travel_mode || false,
      age: detail.date_of_birth ? `${Math.max(0, new Date().getFullYear() - new Date(detail.date_of_birth).getFullYear())} yrs` : '--',
      avatar: (detail.full_name || listEntry?.name || '?').slice(0, 2).toUpperCase(),
    };
  }, [id, patientDetail, patientList]);

  const adherencePct = adherence?.adherence_pct ?? 0;
  const taken = adherence?.taken ?? 0;
  const pending = adherence?.pending ?? 0;
  const total = adherence?.total_scheduled ?? 0;

  const recentAlerts = Array.isArray(alerts) ? alerts.slice(0, 4) : [];

  return (
    <div className="flex flex-col gap-8 py-4">
      <div className="flex flex-col gap-6">
        <button onClick={() => navigate('/caregiver/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors w-fit">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em]">Family Dashboard</span>
        </button>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-[2rem] bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white font-display font-black text-3xl shadow-2xl">
              {patient.avatar}
            </div>
            <div className="flex flex-col gap-1">
              <h1 className="text-4xl font-display font-extrabold tracking-tight text-foreground">{patient.name}</h1>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-muted-foreground text-xs font-bold uppercase tracking-widest">
                <span className="flex items-center gap-1.5"><Heart className="w-3.5 h-3.5 text-destructive" /> {patient.permission}</span>
                <span className="w-1 h-1 bg-muted-foreground/30 rounded-full" />
                <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> {patient.patientCode}</span>
                <span className="w-1 h-1 bg-muted-foreground/30 rounded-full" />
                <span className="flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5" /> {patient.timezone}</span>
              </div>
            </div>
          </div>
          <div className="flex gap-3 w-full md:w-auto">
            <Button variant="outline" onClick={() => setShowCall(true)} className="flex-1 md:flex-none h-12 px-6 rounded-xl border-border/60 font-bold">
              <Phone className="w-4 h-4 mr-2" /> Call
            </Button>
            <Button onClick={() => setShowChat(true)} className="flex-1 md:flex-none h-12 px-6 rounded-xl shadow-lg shadow-primary/20 font-bold">
              <MessageCircle className="w-4 h-4 mr-2" /> Message
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Weekly Adherence" value={`${Math.round(adherencePct)}%`} icon={TrendingUp} color={adherencePct >= 90 ? 'text-emerald-500' : 'text-amber-500'} />
        <StatCard label="Taken / Total" value={`${taken}/${total}`} icon={Activity} color="text-blue-500" />
        <StatCard label="Pending" value={String(pending)} icon={Clock} color="text-orange-500" />
        <StatCard label="Active Meds" value={String(patient.activeMedsCount || 0)} icon={Pill} color="text-primary" />
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 flex flex-col gap-6">
          <Card className="rounded-[2.5rem] overflow-hidden">
            <CardHeader className="bg-muted/30 border-b border-border/40 p-6 flex flex-row items-center justify-between">
              <h3 className="font-display font-bold text-xl flex items-center gap-3">
                <Calendar className="w-5 h-5 text-primary" /> Recent Dose Alerts
              </h3>
              <Badge variant="primary" className="h-6 rounded-full px-3 text-[10px] font-black uppercase">Live</Badge>
            </CardHeader>
            <CardContent className="p-8 space-y-4">
              {isDetailLoading ? (
                <div className="text-sm text-muted-foreground">Loading patient details...</div>
              ) : recentAlerts.length ? (
                recentAlerts.map((alert) => (
                  <div key={alert.id} className="flex gap-4 items-start p-4 rounded-2xl border border-border/60 bg-card">
                    <div className="w-10 h-10 rounded-2xl bg-destructive/10 flex items-center justify-center text-destructive shrink-0">
                      <AlertTriangle className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="font-bold text-foreground">{alert.schedule?.prescription?.medication?.name || 'Medication'}</h4>
                        <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">{new Date(alert.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">Dose {alert.dose_value} {alert.dose_unit} · Status: {alert.status}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground">No recent alerts available for this patient.</div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-[2.5rem] overflow-hidden">
            <CardHeader className="bg-muted/30 border-b border-border/40 p-6 flex flex-row items-center justify-between">
              <h3 className="font-display font-bold text-xl flex items-center gap-3">
                <ShieldAlert className="w-5 h-5 text-primary" /> Care Summary
              </h3>
            </CardHeader>
            <CardContent className="p-8 grid md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-muted/40">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Patient Code</p>
                <p className="font-bold text-lg mt-2">{patient.patientCode}</p>
              </div>
              <div className="p-4 rounded-2xl bg-muted/40">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Hospitalized</p>
                <p className="font-bold text-lg mt-2">{patient.isHospitalized ? `Yes${patient.hospitalName ? ` · ${patient.hospitalName}` : ''}` : 'No'}</p>
              </div>
              <div className="p-4 rounded-2xl bg-muted/40">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Patient Age</p>
                <p className="font-bold text-lg mt-2">{patient.age}</p>
              </div>
              <div className="p-4 rounded-2xl bg-muted/40">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Travel Mode</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="font-bold text-lg">{patient.isTravelMode ? 'Active' : 'Off'}</span>
                  <Button 
                    variant={patient.isTravelMode ? 'default' : 'outline'} 
                    size="sm" 
                    className="h-7 rounded-full px-3 text-xs"
                    onClick={handleToggleTravelMode}
                    disabled={updateMutation.isPending}
                  >
                    {patient.isTravelMode ? 'Turn Off' : 'Turn On'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          {/* AI Adherence Risk Meter */}
          <RiskMeter
            riskScore={riskData?.risk_score}
            riskLevel={riskData?.risk_level}
            confidence={riskData?.confidence}
            source={riskData?.source}
            planNote={riskData?.plan_note}
            isLoading={isRiskLoading}
          />

          {/* AI Behavioral Insights & Explainable Reasons — helps caregiver understand why patient is flagged */}
          <AIInsightsCard
            riskData={riskData}
            insights={insightsData}
            recommendations={recommendationsData}
            isLoading={isInsightsLoading || isRiskLoading || isRecsLoading}
          />

          {/* AI Agent Activity — what the AI Agent has done for this patient */}
          <AgentActivityCard activity={agentActivityData} isLoading={isAgentActivityLoading} />

          <Card className="rounded-[2.5rem] border-dashed border-border/60">
            <CardContent className="p-6">
              <h3 className="font-display font-bold text-lg mb-4 flex items-center gap-2"><Activity className="w-5 h-5 text-primary" /> Linked Data</h3>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between"><span className="text-muted-foreground">Email</span><span className="font-medium">{patient.email}</span></div>
                <div className="flex items-center justify-between"><span className="text-muted-foreground">Timezone</span><span className="font-medium">{patient.timezone}</span></div>
                <div className="flex items-center justify-between"><span className="text-muted-foreground">Permission</span><span className="font-medium capitalize">{patient.permission}</span></div>
                <div className="flex items-center justify-between"><span className="text-muted-foreground">Active Meds</span><span className="font-medium">{patient.activeMedsCount || 0}</span></div>
              </div>
            </CardContent>
          </Card>

          <Button variant="outline" className="h-12 rounded-xl" onClick={() => navigate('/caregiver/alerts')}>
            Open All Alerts
          </Button>
          <Button className="h-12 rounded-xl" onClick={() => navigate('/caregiver/home')}>
            Back to Dashboard
          </Button>
        </div>
      </div>

      {/* Doctor Prescriptions */}
      <div className="mt-8 pt-8 border-t border-border/50">
        <h2 className="text-2xl font-display font-extrabold tracking-tight mb-5 flex items-center gap-3">
          <Stethoscope className="w-7 h-7 text-primary" />
          Doctor Prescriptions
        </h2>
        {loadingRx ? (
          <div className="flex items-center gap-3 text-muted-foreground py-6">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm font-medium">Loading prescriptions…</span>
          </div>
        ) : doctorPrescriptions.length === 0 ? (
          <Card className="rounded-2xl border-dashed border-border/60">
            <CardContent className="p-8 flex flex-col items-center text-center gap-2">
              <Pill className="w-8 h-8 text-muted-foreground/30" />
              <p className="font-bold text-foreground">No doctor prescriptions on file</p>
              <p className="text-sm text-muted-foreground">Prescriptions sent by the patient's doctor will appear here.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {doctorPrescriptions.map((rx) => (
              <Card key={rx.id} className="rounded-2xl border-border/50">
                <CardContent className="p-5 flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="font-bold text-foreground">{rx.medication_name || 'Medication'}</h4>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        From <span className="font-semibold text-foreground">{rx.doctor_name || 'Doctor'}</span>
                        {rx.created_at && ` · ${new Date(rx.created_at).toLocaleDateString()}`}
                      </p>
                    </div>
                    {rx.is_accepted === true  && <Badge variant="success"   className="h-5 px-2 text-[9px] font-black uppercase flex-shrink-0">Accepted</Badge>}
                    {rx.is_accepted === false && <Badge variant="danger"    className="h-5 px-2 text-[9px] font-black uppercase flex-shrink-0">Rejected</Badge>}
                    {rx.is_accepted == null   && <Badge variant="warning"   className="h-5 px-2 text-[9px] font-black uppercase flex-shrink-0">Pending</Badge>}
                  </div>
                  {rx.dosage       && <p className="text-sm text-muted-foreground">Dosage: <span className="font-semibold text-foreground">{rx.dosage}</span></p>}
                  {rx.instructions && <p className="text-sm text-muted-foreground italic">"{rx.instructions}"</p>}
                  <div className="flex gap-2 mt-1 text-xs text-muted-foreground">
                    {rx.is_accepted === true && <span className="flex items-center gap-1 text-success"><CheckCircle2 className="w-3 h-3" /> Patient accepted this prescription</span>}
                    {rx.is_accepted === false && <span className="flex items-center gap-1 text-destructive"><XCircle className="w-3 h-3" /> Patient rejected this prescription</span>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className="mt-8 pt-8 border-t border-border/50">
        <h2 className="text-3xl font-display font-extrabold tracking-tight mb-6 flex items-center gap-3">
          <TrendingUp className="w-8 h-8 text-primary" />
          Detailed Adherence Report
        </h2>
        <Reports patientId={id} />
      </div>

      {/* Chat Drawer — slides in from right */}
      {showChat && (
        <ChatDrawer
          patientId={id}
          patientName={patient.name}
          onClose={() => setShowChat(false)}
        />
      )}

      {/* Call Modal — fullscreen overlay */}
      {showCall && (
        <CallModal
          patientId={id}
          patientName={patient.name}
          onClose={() => setShowCall(false)}
        />
      )}
    </div>
  );
}
