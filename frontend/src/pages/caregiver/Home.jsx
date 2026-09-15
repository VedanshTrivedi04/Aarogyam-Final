import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import {
  Users, Bell, Activity, Heart, Clock, ChevronRight,
  Eye, Plus, BarChart3, Settings, ShieldAlert, Pill,
  Smartphone, X, Mail, Phone, Siren,
  QrCode, Loader2, UserPlus, Sparkles, CheckCircle2, AlertCircle
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useCaregiverPatients, useAddCaregiverPatient } from '@/hooks/useCaregiver';
import { useCaregiverDashboardSummary, useCaregiverCohort } from '@/hooks/useCaregiverAnalytics';
import { useCaregiverDevices, useDispenserCompartments, useDeviceDetail, useDoseAlerts } from '@/hooks/useIoT';

const Ring = ({ pct, size = 64 }) => {
  const safePct = Number.isFinite(pct) ? pct : 0;
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="w-full h-full -rotate-90">
        <circle className="text-muted/30" strokeWidth="5" stroke="currentColor" fill="transparent" r={r} cx={size / 2} cy={size / 2} />
        <motion.circle
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (safePct / 100) * c }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
          className={safePct >= 90 ? 'text-emerald-500' : safePct >= 75 ? 'text-amber-500' : 'text-red-500'}
          strokeWidth="5"
          strokeDasharray={c}
          strokeLinecap="round"
          stroke="currentColor"
          fill="transparent"
          r={r}
          cx={size / 2}
          cy={size / 2}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display font-bold text-[10px]">{safePct}%</span>
    </div>
  );
};

const PatientCard = ({ patient, onClick }) => (
  <motion.div
    whileHover={{ y: -4 }}
    onClick={() => onClick(patient.id)}
    className="bg-card rounded-[2rem] border border-border/60 shadow-elevation-1 hover:shadow-elevation-3 transition-all cursor-pointer overflow-hidden group"
  >
    <div className="p-6">
      <div className="flex items-start gap-4 mb-5">
        <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${patient.color} flex items-center justify-center text-white font-bold shadow-lg flex-shrink-0 text-xl`}>
          {patient.avatar}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="font-display font-bold text-foreground text-lg truncate">{patient.name}</h3>
            <span className={`w-2 h-2 rounded-full shrink-0 ${patient.status === 'ATTENTION' || patient.status === 'needs-attention' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
          </div>
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-widest">{patient.patientCode}</p>
          <p className="text-[10px] text-muted-foreground font-semibold mt-1">Permission: {patient.permission}</p>
        </div>
        <Ring pct={patient.adherence} size={56} />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="p-3 bg-muted/40 rounded-2xl text-center">
          <p className="text-[9px] font-black uppercase tracking-tighter text-muted-foreground mb-1">Meds</p>
          <p className="font-bold text-sm">{patient.activeMedsCount || 0}</p>
        </div>
        <div className="p-3 bg-muted/40 rounded-2xl text-center">
          <p className="text-[9px] font-black uppercase tracking-tighter text-muted-foreground mb-1">Risk</p>
          <p className={`font-bold text-sm ${patient.openAnomalies > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>{patient.openAnomalies > 0 ? 'Attention' : 'Stable'}</p>
        </div>
        <div className="p-3 bg-muted/40 rounded-2xl text-center">
          <p className="text-[9px] font-black uppercase tracking-tighter text-muted-foreground mb-1">Code</p>
          <p className="font-bold text-sm text-primary truncate">{patient.patientCode || '--'}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground font-medium bg-muted/30 p-3 rounded-xl">
        <Clock className="w-3.5 h-3.5 text-primary" /> {patient.timezone || 'Timezone unavailable'}
      </div>
    </div>
    <div className="px-6 py-4 border-t border-border/40 flex justify-between items-center bg-primary/5 group-hover:bg-primary/10 transition-colors">
      <span className="text-[10px] font-black uppercase tracking-widest text-primary flex items-center gap-2">
        <Eye className="w-3.5 h-3.5" /> Clinical Profile
      </span>
      <ChevronRight className="w-4 h-4 text-primary group-hover:translate-x-1 transition-transform" />
    </div>
  </motion.div>
);

export default function CaregiverHome() {
  const navigate = useNavigate();
  const { data: patientRows = [], isLoading: isLoadingPatients } = useCaregiverPatients();
  const { data: summary } = useCaregiverDashboardSummary();
  const { data: cohort = [], isLoading: isLoadingCohort } = useCaregiverCohort();
  const { data: devices = [], isLoading: isLoadingDevices } = useCaregiverDevices();
  const firstDevice = devices?.[0];
  const { data: compartments = [] } = useDispenserCompartments(firstDevice?.id);
  const { data: deviceDetail } = useDeviceDetail(firstDevice?.id);
  const { data: doseAlertsData } = useDoseAlerts();

  const [isAddPatientOpen, setIsAddPatientOpen] = useState(false);
  const [isEmergencyPlanOpen, setIsEmergencyPlanOpen] = useState(false);
  const [linkMethod, setLinkMethod] = useState('create'); // 'code' | 'email' | 'create'
  const [formData, setFormData] = useState({
    code: '',
    email: '',
    phone: '',
    fullName: '',
    password: ''
  });
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const addPatientMutation = useAddCaregiverPatient();

  const handleLinkSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    const payload = {};
    if (linkMethod === 'create') {
      payload.create_new = true;
      payload.full_name = formData.fullName.trim();
      payload.email = formData.email.trim();
      payload.phone_number = formData.phone.trim();
      payload.password = formData.password;
    } else if (linkMethod === 'code') {
      payload.patient_code = formData.code.trim();
    } else if (linkMethod === 'email') {
      payload.email = formData.email.trim();
    }

    addPatientMutation.mutate(payload, {
      onSuccess: (data) => {
        setSuccessMsg(data?.message || 'Patient successfully linked!');
        setTimeout(() => {
          setIsAddPatientOpen(false);
          setFormData({ code: '', email: '', phone: '', fullName: '', password: '' });
          setSuccessMsg('');
        }, 1500);
      },
      onError: (err) => {
        setErrorMsg(err?.message || 'Failed to link patient. Please try again.');
      }
    });
  };

  const patients = useMemo(() => {
    const cohortMap = new Map(cohort.map((row) => [row.patient_code, row]));
    
    const merged = patientRows.map((p) => {
      const row = cohortMap.get(p.patientCode) || {};
      return {
        id: p.id,
        name: p.name,
        patientCode: p.patientCode,
        adherence: Math.round(row.adherence_pct_7d ?? p.adherence ?? 0),
        openAnomalies: row.open_anomalies ?? 0,
        status: row.status || p.status,
        permission: p.permission || 'view_only',
        timezone: p.timezone || 'Unknown',
        activeMedsCount: p.activeMedsCount || 0,
        avatar: (p.name || '?').slice(0, 2).toUpperCase(),
        color: (row.status || p.status) === 'ATTENTION' || (row.status || p.status) === 'needs-attention' ? 'from-amber-500 to-orange-500' : 'from-blue-500 to-cyan-500',
      };
    });

    if (merged.length > 0) return merged;

    return cohort.map((row) => ({
      id: row.patient_id,
      name: row.patient_name,
      patientCode: row.patient_code,
      adherence: Math.round(row.adherence_pct_7d ?? 0),
      openAnomalies: row.open_anomalies ?? 0,
      status: row.status,
      permission: 'view_only',
      timezone: 'Unknown',
      activeMedsCount: 0,
      avatar: (row.patient_name || '?').slice(0, 2).toUpperCase(),
      color: row.status === 'ATTENTION' ? 'from-amber-500 to-orange-500' : 'from-blue-500 to-cyan-500',
    }));
  }, [cohort, patientRows]);

  const lowRefillCompartments = useMemo(() => compartments.filter(c => c.current_pill_count < 5), [compartments]);
  const totalPatients = summary?.total_patients ?? patients.length;
  const overallAdherence = summary?.overall_adherence_pct ?? (patients.length ? Math.round(patients.reduce((sum, patient) => sum + patient.adherence, 0) / patients.length) : 0);
  const needsAttention = (summary?.needs_attention ?? patients.filter((patient) => patient.openAnomalies > 0 || patient.adherence < 70).length) + (lowRefillCompartments.length > 0 ? 1 : 0);

  const deviceIndicator = useMemo(() => {
    if (!firstDevice) return { label: 'No device linked', tone: 'text-muted-foreground' };
    return {
      label: firstDevice.is_online ? 'Device online' : 'Device offline',
      tone: firstDevice.is_online ? 'text-emerald-600' : 'text-amber-600',
    };
  }, [firstDevice]);

  const loading = isLoadingPatients || isLoadingCohort || isLoadingDevices;

  return (
    <div className="flex flex-col gap-8 py-4 max-w-[1600px] mx-auto w-full">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-display font-extrabold flex items-center gap-3 tracking-tight">
            <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center shadow-inner">
              <Users className="w-6 h-6 text-primary" />
            </div>
            Family Overview
          </h1>
          <p className="text-muted-foreground font-medium mt-1">Monitoring {loading ? '...' : totalPatients} linked patients under your clinical care.</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" className="h-12 px-6 rounded-xl border-destructive/20 text-destructive hover:bg-destructive/5 font-bold" onClick={() => setIsEmergencyPlanOpen(true)}>
            <ShieldAlert className="w-5 h-5 mr-2" /> Emergency Plan
          </Button>
          <Button variant="outline" className="h-12 px-6 rounded-xl font-bold text-primary border-primary/20 hover:bg-primary/5" onClick={() => setIsAddPatientOpen(true)}>
            <UserPlus className="w-5 h-5 mr-2" /> Add Patient
          </Button>
          <Button className="h-12 px-6 rounded-xl shadow-lg shadow-primary/20 font-bold" onClick={() => navigate('/caregiver/compartments')}>
            <Plus className="w-5 h-5 mr-2" /> Device Logic
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: Heart, label: 'Avg Adherence', value: `${overallAdherence}%`, sub: '7-day analytics', color: 'text-emerald-600' },
          { icon: Bell, label: 'Active Alerts', value: String(needsAttention), sub: 'Need attention', color: 'text-destructive' },
          { icon: Pill, label: 'Total Meds', value: String(patients.reduce((sum, patient) => sum + (patient.activeMedsCount || 0), 0)), sub: 'Across patients', color: 'text-primary' },
          { icon: Activity, label: 'Devices', value: String(devices?.length || 0), sub: 'Linked hardware', color: 'text-orange-500' },
        ].map((stat) => (
          <Card key={stat.label} className="hover:shadow-elevation-2 transition-all border-border/50 group">
            <CardContent className="p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                  <stat.icon className="w-5 h-5" />
                </div>
                <span className="text-[10px] text-muted-foreground font-black uppercase tracking-widest">{stat.label}</span>
              </div>
              <p className={`text-3xl font-display font-black ${stat.color}`}>{stat.value}</p>
              <p className="text-[11px] text-muted-foreground font-semibold mt-1">{stat.sub}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left (lg:col-span-2): Active Patients + Live Activity Feed + Compartments */}
        <div className="lg:col-span-2 flex flex-col gap-8">
          {/* Active Patients Section */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-bold text-2xl tracking-tight">Active Patients</h2>
              <Link to="/caregiver/alerts" className="text-sm font-bold text-primary hover:underline flex items-center gap-1">
                View All Alerts <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {loading ? (
                <div className="md:col-span-2 text-sm text-muted-foreground p-6 bg-card rounded-2xl border border-border/50">Loading patient cohort...</div>
              ) : patients.length ? (
                patients.map((patient) => (
                  <PatientCard key={patient.id} patient={patient} onClick={(id) => navigate(`/caregiver/patient/${id}`)} />
                ))
              ) : (
                <div className="md:col-span-2 flex flex-col items-center justify-center p-12 bg-card rounded-[2.5rem] border border-border/50 text-center shadow-inner relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent pointer-events-none" />
                  <div className="w-16 h-16 rounded-3xl bg-primary/10 flex items-center justify-center text-primary mb-4 relative z-10">
                    <UserPlus className="w-8 h-8" />
                  </div>
                  <h3 className="font-display font-extrabold text-xl mb-2 relative z-10 text-foreground">No Active Patients</h3>
                  <p className="text-muted-foreground text-sm max-w-sm mb-6 relative z-10 leading-relaxed font-medium">
                    You don't have any patients linked to your clinical dashboard. Add a patient using their email, patient code, or phone number to start tracking adherence.
                  </p>
                  <Button className="rounded-xl h-11 px-6 shadow-lg shadow-primary/20 relative z-10 font-bold" onClick={() => setIsAddPatientOpen(true)}>
                    <Plus className="w-4 h-4 mr-2" /> Add Your First Patient
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Live Clinical Alerts & Dose Activity (Scrollable Container) */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="font-display font-bold text-xl tracking-tight flex items-center gap-2 text-foreground">
                  <Activity className="w-5 h-5 text-primary" /> Live Clinical Alerts &amp; Dose Activity
                </h3>
                <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest bg-success/10 text-success border border-success/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" /> Live Stream
                </span>
              </div>
              <Link to="/caregiver/alerts" className="text-xs font-bold text-primary hover:underline flex items-center gap-1">
                Full Feed <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <Card className="rounded-[2rem] border border-border/60 shadow-elevation-1 overflow-hidden h-[300px] flex flex-col bg-card">
              <CardContent className="p-5 overflow-y-auto flex-1 space-y-3">
                {doseAlertsData?.alerts && doseAlertsData.alerts.length > 0 ? (
                  doseAlertsData.alerts.map((alert, idx) => (
                    <div
                      key={alert.session_id || idx}
                      className="p-4 rounded-2xl border border-border/60 bg-muted/20 hover:bg-muted/40 transition-all flex items-center justify-between gap-4"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                          alert.dose_status === 'missed' ? 'bg-destructive/10 text-destructive' : 'bg-amber-500/10 text-amber-600'
                        }`}>
                          <AlertCircle className="w-5 h-5" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-sm text-foreground truncate">{alert.device_name || 'Smart Dispenser'}</span>
                            <Badge variant={alert.dose_status === 'missed' ? 'danger' : 'warning'} className="text-[9px] uppercase font-black tracking-wider">
                              Slot {alert.compartment_number} · {alert.dose_status}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5 truncate">
                            Scheduled dose at {new Date(alert.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => navigate('/caregiver/devices')}
                        className="h-8 px-3 text-xs font-bold rounded-lg shrink-0 border-primary/30 text-primary hover:bg-primary/10"
                      >
                        Inspect
                      </Button>
                    </div>
                  ))
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-success/10 text-success flex items-center justify-center">
                      <CheckCircle2 className="w-6 h-6" />
                    </div>
                    <h4 className="font-bold text-sm text-foreground">All Patients on Schedule</h4>
                    <p className="text-xs text-muted-foreground max-w-sm">
                      No active medication alarms or dispenser anomalies detected. Real-time patient monitoring is functioning normally.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Smart Dispenser Compartment Status (Hardware Live View) */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-xl tracking-tight flex items-center gap-2 text-foreground">
                <Pill className="w-5 h-5 text-primary" /> Dispenser Compartment Status
              </h3>
              <Link to="/caregiver/compartments" className="text-xs font-bold text-primary hover:underline flex items-center gap-1">
                Manage Slots <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((slotNum) => {
                const comp = compartments.find(c => c.compartment_number === slotNum);
                const isLow = comp && comp.current_pill_count < 5;
                const slotTimes = { 1: 'Morning (08:00)', 2: 'Afternoon (13:00)', 3: 'Evening (18:00)', 4: 'Night (21:00)' };
                return (
                  <Card key={slotNum} className="border border-border/60 bg-card rounded-2xl p-4 hover:border-primary/40 transition-all shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Slot {slotNum}</span>
                      {isLow ? (
                        <span className="text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-destructive/10 text-destructive border border-destructive/20">
                          Low Refill
                        </span>
                      ) : comp?.current_pill_count > 0 ? (
                        <span className="text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-success/10 text-success border border-success/20">
                          OK
                        </span>
                      ) : (
                        <span className="text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          Empty
                        </span>
                      )}
                    </div>
                    <p className="text-2xl font-display font-black text-foreground">
                      {comp?.current_pill_count ?? 0} <span className="text-xs font-normal text-muted-foreground">pills</span>
                    </p>
                    <p className="text-xs font-semibold text-primary truncate mt-1">
                      {comp?.medication_name || comp?.time_slot_display || 'Standard Dispense'}
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1">
                      <Clock className="w-3 h-3 text-muted-foreground/60 shrink-0" /> {slotTimes[slotNum]}
                    </p>
                  </Card>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right (lg:col-span-1): Device Control, Emergency & Management */}
        <div className="flex flex-col gap-6">
          <h2 className="font-display font-bold text-2xl tracking-tight">Device Control</h2>

          <Card className="bg-primary text-white border-none shadow-2xl shadow-primary/20 rounded-[2.5rem] overflow-hidden group">
            <CardContent className="p-8 flex flex-col gap-6 relative">
              <div className="absolute right-0 top-0 w-32 h-32 bg-white/10 rounded-full translate-x-1/2 -translate-y-1/2 blur-2xl" />
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center backdrop-blur-xl">
                  <Pill className="w-8 h-8" />
                </div>
                <div>
                  <h4 className="font-bold text-lg">{firstDevice?.device_name || 'No device linked'}</h4>
                  <p className="text-xs opacity-70 font-semibold uppercase tracking-widest">{firstDevice?.device_type || 'Connect a dispenser to unlock live controls'}</p>
                </div>
              </div>

              <div className={`text-xs font-bold uppercase tracking-widest ${deviceIndicator.tone}`}>
                {deviceIndicator.label}
              </div>

              {firstDevice ? (
                <>
                  <div className="grid grid-cols-3 gap-3 text-[10px] font-semibold uppercase tracking-widest">
                    <div className="bg-white/10 rounded-2xl p-3 text-center">Battery {firstDevice.battery_level ?? '--'}%</div>
                    <div className="bg-white/10 rounded-2xl p-3 text-center">Firmware {firstDevice.firmware_version || '--'}</div>
                    <div className="bg-white/10 rounded-2xl p-3 text-center">Device {firstDevice.is_active ? 'Active' : 'Paused'}</div>
                  </div>
                  {lowRefillCompartments.length > 0 && (
                    <div className="bg-amber-500/20 border border-amber-400/50 rounded-2xl p-4 flex flex-col gap-2">
                      <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-widest">
                        <AlertCircle className="w-4 h-4" />
                        <span>Refill Required</span>
                      </div>
                      <p className="text-sm font-medium">
                        Compartment {lowRefillCompartments.map(c => c.compartment_number).join(', ')} is running low on pills.
                      </p>
                    </div>
                  )}
                </>
              ) : null}

              <div className="space-y-3">
                <Button onClick={() => navigate('/caregiver/devices')} className="w-full h-12 bg-white !text-[#0B6E7A] hover:bg-white/90 font-black uppercase tracking-widest text-xs rounded-xl">
                  Manage Dispenser
                </Button>
                <Button onClick={() => navigate('/caregiver/devices')} variant="ghost" className="w-full h-12 text-white hover:bg-white/10 font-black uppercase tracking-widest text-xs border border-white/20 rounded-xl" disabled={!firstDevice}>
                  Commands &amp; Alerts
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Emergency Escalation Protocol Card */}
          <Card className="rounded-[2.5rem] border border-destructive/20 bg-destructive/5 overflow-hidden shadow-sm">
            <CardContent className="p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-destructive/10 flex items-center justify-center text-destructive shrink-0">
                    <Siren className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-foreground">Emergency Hotline</h4>
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Escalation Protocol</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setIsEmergencyPlanOpen(true)}
                  className="h-8 px-3 text-xs font-bold rounded-xl border-destructive/30 text-destructive hover:bg-destructive/10"
                >
                  Contacts
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs font-bold">
                <a href="tel:108" className="flex items-center gap-2 p-3 bg-card rounded-xl border border-border/60 hover:border-destructive/40 transition-colors">
                  <Phone className="w-3.5 h-3.5 text-destructive shrink-0" />
                  <div>
                    <span className="text-foreground block leading-tight">Ambulance</span>
                    <span className="text-[10px] text-muted-foreground font-normal">Dial 108</span>
                  </div>
                </a>
                <a href="tel:112" className="flex items-center gap-2 p-3 bg-card rounded-xl border border-border/60 hover:border-destructive/40 transition-colors">
                  <Phone className="w-3.5 h-3.5 text-destructive shrink-0" />
                  <div>
                    <span className="text-foreground block leading-tight">National</span>
                    <span className="text-[10px] text-muted-foreground font-normal">Dial 112</span>
                  </div>
                </a>
              </div>
            </CardContent>
          </Card>

          {/* Management Console */}
          <Card className="rounded-[2.5rem] shadow-sm">
            <CardContent className="p-8">
              <h3 className="font-display font-bold text-lg mb-6 uppercase tracking-widest text-[11px] opacity-60">Management Console</h3>
              <div className="grid grid-cols-1 gap-3">
                {[
                  { icon: BarChart3, label: 'Weekly Reports', to: '/caregiver/alerts' },
                  { icon: Smartphone, label: 'IoT Device Manager', to: '/caregiver/devices' },
                  { icon: Pill, label: 'Compartment Setup', to: '/caregiver/compartments' },
                  { icon: Settings, label: 'Clinical Settings', to: '/caregiver/settings' },
                ].map((item) => (
                  <Link key={item.label} to={item.to}>
                    <button className="w-full flex items-center justify-between p-4 bg-muted/40 hover:bg-secondary rounded-2xl transition-all group">
                      <div className="flex items-center gap-3">
                        <item.icon className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                        <span className="text-sm font-bold text-foreground">{item.label}</span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:translate-x-1 transition-transform" />
                    </button>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Add Patient Modal */}
      {isAddPatientOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm overflow-y-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative w-full max-w-lg bg-card rounded-[2.5rem] border border-border/80 shadow-2xl p-8 overflow-hidden"
          >
            {/* Background Accent Glow */}
            <div className="absolute right-0 top-0 w-32 h-32 bg-primary/10 rounded-full translate-x-1/3 -translate-y-1/3 blur-2xl pointer-events-none" />
            <div className="absolute left-0 bottom-0 w-32 h-32 bg-secondary/20 rounded-full -translate-x-1/3 translate-y-1/3 blur-2xl pointer-events-none" />

            {/* Header */}
            <div className="flex justify-between items-start mb-6 relative">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <UserPlus className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-display font-extrabold text-2xl tracking-tight text-foreground">Add New Patient</h3>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mt-0.5">Caregiver Link Program</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setIsAddPatientOpen(false);
                  setFormData({ code: '', email: '', phone: '', fullName: '', password: '' });
                  setErrorMsg('');
                  setSuccessMsg('');
                }}
                className="w-8 h-8 rounded-full bg-muted/40 hover:bg-muted/80 flex items-center justify-center transition-colors text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content / Form */}
            {successMsg ? (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center text-center py-8"
              >
                <div className="w-20 h-20 rounded-full bg-emerald-500/10 flex items-center justify-center mb-6">
                  <CheckCircle2 className="w-10 h-10 text-emerald-500" />
                </div>
                <h4 className="font-display font-extrabold text-xl mb-2 text-foreground">Successfully Linked!</h4>
                <p className="text-muted-foreground text-sm max-w-xs">{successMsg}</p>
              </motion.div>
            ) : (
              <form onSubmit={handleLinkSubmit} className="space-y-6 relative">
                {/* Method Tabs */}
                <div className="bg-muted/50 p-1.5 rounded-2xl grid grid-cols-3 gap-1 relative z-10">
                  {[
                    { id: 'create', label: 'Create New', icon: UserPlus },
                    { id: 'code', label: 'By Code', icon: QrCode },
                    { id: 'email', label: 'By Email', icon: Mail },
                  ].map((method) => {
                    const Icon = method.icon;
                    const isActive = linkMethod === method.id;
                    return (
                      <button
                        key={method.id}
                        type="button"
                        onClick={() => {
                          setLinkMethod(method.id);
                          setErrorMsg('');
                        }}
                        className={`relative py-3 rounded-xl flex flex-col items-center justify-center gap-1.5 text-xs font-bold transition-all ${
                          isActive
                            ? 'bg-card text-primary shadow-elevation-1 border border-border/40'
                            : 'text-muted-foreground hover:text-foreground hover:bg-card/30'
                        }`}
                      >
                        <Icon className={`w-4 h-4 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                        {method.label}
                      </button>
                    );
                  })}
                </div>

                {/* Dynamic Input Field */}
                <div className="space-y-4">
                  {linkMethod === 'create' ? (
                    <>
                      <div className="space-y-2">
                        <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block">Full Name</label>
                        <input
                          type="text"
                          required
                          placeholder="Patient's Full Name"
                          value={formData.fullName}
                          onChange={(e) => setFormData(p => ({ ...p, fullName: e.target.value }))}
                          className="w-full h-12 pl-4 pr-4 rounded-xl bg-muted/30 border border-border/80 focus:border-primary/80 focus:ring-2 focus:ring-primary/10 transition-all font-semibold outline-none text-foreground placeholder:text-muted-foreground/50"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block">Email Address</label>
                        <input
                          type="email"
                          required
                          placeholder="patient@example.com"
                          value={formData.email}
                          onChange={(e) => setFormData(p => ({ ...p, email: e.target.value }))}
                          className="w-full h-12 pl-4 pr-4 rounded-xl bg-muted/30 border border-border/80 focus:border-primary/80 focus:ring-2 focus:ring-primary/10 transition-all font-semibold outline-none text-foreground placeholder:text-muted-foreground/50"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block">Mobile Number</label>
                        <input
                          type="tel"
                          required
                          placeholder="+1234567890"
                          value={formData.phone}
                          onChange={(e) => setFormData(p => ({ ...p, phone: e.target.value }))}
                          className="w-full h-12 pl-4 pr-4 rounded-xl bg-muted/30 border border-border/80 focus:border-primary/80 focus:ring-2 focus:ring-primary/10 transition-all font-semibold outline-none text-foreground placeholder:text-muted-foreground/50"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block">Password</label>
                        <input
                          type="password"
                          required
                          placeholder="Create a password for them"
                          value={formData.password}
                          onChange={(e) => setFormData(p => ({ ...p, password: e.target.value }))}
                          className="w-full h-12 pl-4 pr-4 rounded-xl bg-muted/30 border border-border/80 focus:border-primary/80 focus:ring-2 focus:ring-primary/10 transition-all font-semibold outline-none text-foreground placeholder:text-muted-foreground/50"
                        />
                      </div>
                    </>
                  ) : linkMethod === 'code' ? (
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block">Patient Medical Code</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. PAT123"
                        value={formData.code}
                        onChange={(e) => setFormData(p => ({ ...p, code: e.target.value }))}
                        className="w-full h-14 pl-5 pr-5 rounded-2xl bg-muted/30 border border-border/80 focus:border-primary/80 focus:ring-4 focus:ring-primary/10 transition-all font-semibold outline-none text-foreground placeholder:text-muted-foreground/50"
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block">Patient Email Address</label>
                      <input
                        type="email"
                        required
                        placeholder="patient@example.com"
                        value={formData.email}
                        onChange={(e) => setFormData(p => ({ ...p, email: e.target.value }))}
                        className="w-full h-14 pl-5 pr-5 rounded-2xl bg-muted/30 border border-border/80 focus:border-primary/80 focus:ring-4 focus:ring-primary/10 transition-all font-semibold outline-none text-foreground placeholder:text-muted-foreground/50"
                      />
                    </div>
                  )}
                </div>

                {/* Educational Banner */}
                <div className="p-4 bg-primary/5 rounded-2xl border border-primary/10 flex gap-3">
                  <Sparkles className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                  <p className="text-xs text-muted-foreground font-semibold leading-relaxed">
                    Linking allows you to monitor their medication adherence, track AI risk ratings, and coordinate medical reminders directly.
                  </p>
                </div>

                {/* Error Banner */}
                {errorMsg && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 bg-destructive/10 rounded-2xl border border-destructive/20 flex gap-3 text-destructive"
                  >
                    <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                    <p className="text-xs font-bold leading-relaxed">{errorMsg}</p>
                  </motion.div>
                )}

                {/* Submit button */}
                <div className="flex gap-3 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1 h-12 rounded-xl font-bold"
                    onClick={() => {
                      setIsAddPatientOpen(false);
                      setFormData({ code: '', email: '', phone: '', fullName: '', password: '' });
                      setErrorMsg('');
                    }}
                    disabled={addPatientMutation.isPending}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="flex-1 h-12 rounded-xl font-bold shadow-lg shadow-primary/20"
                    disabled={addPatientMutation.isPending || (linkMethod === 'create' ? (!formData.email || !formData.password || !formData.fullName) : linkMethod === 'code' ? !formData.code : !formData.email)}
                  >
                    {addPatientMutation.isPending ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Linking...
                      </>
                    ) : (
                      'Link Patient'
                    )}
                  </Button>
                </div>
              </form>
            )}
          </motion.div>
        </div>
      )}

      {/* Emergency Plan Modal */}
      {isEmergencyPlanOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm overflow-y-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative w-full max-w-lg bg-card rounded-[2.5rem] border border-border/80 shadow-2xl p-8"
          >
            <div className="flex justify-between items-start mb-6">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-destructive/10 flex items-center justify-center">
                  <Siren className="w-6 h-6 text-destructive" />
                </div>
                <div>
                  <h3 className="font-display font-extrabold text-2xl tracking-tight text-foreground">Emergency Plan</h3>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mt-0.5">Quick access to critical contacts</p>
                </div>
              </div>
              <button
                onClick={() => setIsEmergencyPlanOpen(false)}
                className="w-8 h-8 rounded-full bg-muted/40 hover:bg-muted/80 flex items-center justify-center transition-colors text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 mb-6">
              <a href="tel:108" className="flex items-center justify-between p-4 rounded-2xl bg-destructive/10 hover:bg-destructive/15 transition-colors">
                <div className="flex items-center gap-3">
                  <Phone className="w-4 h-4 text-destructive" />
                  <div>
                    <p className="font-bold text-sm text-destructive">Ambulance (India)</p>
                    <p className="text-xs text-muted-foreground">Dial 108</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-destructive" />
              </a>
              <a href="tel:112" className="flex items-center justify-between p-4 rounded-2xl bg-destructive/10 hover:bg-destructive/15 transition-colors">
                <div className="flex items-center gap-3">
                  <Phone className="w-4 h-4 text-destructive" />
                  <div>
                    <p className="font-bold text-sm text-destructive">National Emergency Number</p>
                    <p className="text-xs text-muted-foreground">Dial 112</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-destructive" />
              </a>
              {deviceDetail?.chemist_phone && (
                <a href={`tel:${deviceDetail.chemist_phone}`} className="flex items-center justify-between p-4 rounded-2xl bg-muted/40 hover:bg-secondary transition-colors">
                  <div className="flex items-center gap-3">
                    <Phone className="w-4 h-4 text-primary" />
                    <div>
                      <p className="font-bold text-sm text-foreground">{deviceDetail.chemist_name || 'Pharmacy / Chemist'}</p>
                      <p className="text-xs text-muted-foreground">{deviceDetail.chemist_phone}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                </a>
              )}
            </div>

            <h4 className="text-xs font-black uppercase tracking-widest text-muted-foreground mb-3">Linked Patients</h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {patients.length ? patients.map((patient) => (
                <button
                  key={patient.id}
                  onClick={() => { setIsEmergencyPlanOpen(false); navigate(`/caregiver/patient/${patient.id}`); }}
                  className="w-full flex items-center justify-between p-3 rounded-xl bg-muted/40 hover:bg-secondary transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${patient.color} flex items-center justify-center text-white font-bold text-xs`}>
                      {patient.avatar}
                    </div>
                    <span className="font-bold text-sm">{patient.name}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                </button>
              )) : (
                <p className="text-sm text-muted-foreground">No linked patients yet.</p>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
