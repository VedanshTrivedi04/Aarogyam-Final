import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldAlert, Bell, AlertTriangle,
  Search, ArrowLeft, MessageSquare, RotateCw, Loader2
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useCaregiverPatients, useCaregiverPatientsData } from '@/hooks/useCaregiver';
import { useDoseAlerts } from '@/hooks/useIoT';
import { useNotifications } from '@/hooks/useNotifications';

const ALERT_STYLES = {
  critical: { bg: 'bg-destructive/5 border-destructive/20', text: 'text-destructive', iconBg: 'bg-destructive/10' },
  warning: { bg: 'bg-accent/5 border-accent/20', text: 'text-accent', iconBg: 'bg-accent/10' },
  security: { bg: 'bg-primary/5 border-primary/20', text: 'text-primary', iconBg: 'bg-primary/10' },
  success: { bg: 'bg-success/5 border-success/20', text: 'text-success', iconBg: 'bg-success/10' },
  info: { bg: 'bg-muted/50 border-border/50', text: 'text-foreground', iconBg: 'bg-muted' },
};

const AlertCard = ({ alert, onAction }) => {
  const s = ALERT_STYLES[alert.type] || ALERT_STYLES.info;
  const Icon = alert.icon || (alert.type === 'critical' ? ShieldAlert : alert.type === 'warning' ? AlertTriangle : Bell);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className={`p-6 rounded-[2rem] border ${s.bg} flex flex-col md:flex-row gap-6 items-start md:items-center group transition-all hover:shadow-elevation-2`}
    >
      <div className={`w-14 h-14 rounded-2xl ${s.iconBg} flex items-center justify-center shrink-0`}>
        <Icon className={`w-7 h-7 ${s.text}`} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant={alert.type === 'critical' ? 'danger' : alert.type === 'warning' ? 'warning' : 'primary'} className="h-5 px-2 text-[9px] font-black uppercase tracking-widest">
            {alert.type}
          </Badge>
          <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">{alert.time}</span>
        </div>
        <h4 className="font-bold text-lg text-foreground mb-1">
          {alert.patient} <span className="text-muted-foreground font-medium text-sm">{alert.subtitle ? `(${alert.subtitle})` : ''}</span>
        </h4>
        <p className="text-sm text-foreground/80 leading-relaxed font-medium">{alert.message}</p>
      </div>

      <div className="flex gap-2 w-full md:w-auto">
        <Button onClick={() => onAction(alert)} className={`flex-1 md:flex-none h-11 px-6 rounded-xl font-bold text-xs uppercase tracking-widest ${alert.type === 'critical' ? 'bg-destructive hover:bg-destructive/90 shadow-lg shadow-destructive/20' : ''}`}>
          {alert.action}
        </Button>
        <button className="h-11 w-11 rounded-xl bg-card border border-border/60 flex items-center justify-center text-muted-foreground hover:text-primary transition-colors">
          <MessageSquare className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
};

export default function AlertsFeed() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data: patients = [], isLoading: isPatientsLoading } = useCaregiverPatients();
  const { alertsQueries } = useCaregiverPatientsData(patients.map((patient) => patient.id));
  const { data: deviceAlerts, isLoading: isDeviceLoading } = useDoseAlerts();
  const { data: notificationsData, isLoading: isNotifLoading } = useNotifications();

  const isAnyLoading = isPatientsLoading || isDeviceLoading || alertsQueries.some((q) => q.isLoading);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const alerts = useMemo(() => {
    const patientNameById = new Map(patients.map((patient) => [patient.id, patient.name]));
    const list = [];
    const seenIds = new Set();

    // 1. Patient Missed Dose & Clinical Alerts
    alertsQueries.forEach((query, index) => {
      const items = Array.isArray(query.data) ? query.data : [];
      const patient = patients[index];
      items.forEach((job) => {
        if (job?.id && !seenIds.has(`patient-${job.id}`)) {
          seenIds.add(`patient-${job.id}`);
          const medName = job.medication_name || job.schedule?.prescription?.medication?.name || 'Medication';
          const pName = patient?.name || patientNameById.get(patient?.id) || 'Patient';
          list.push({
            id: `patient-${job.id}`,
            type: 'critical',
            patient: pName,
            subtitle: patient?.patientCode || job.patient_code,
            message: `Missed ${medName} (${job.dose_value} ${job.dose_unit})`,
            time: new Date(job.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            timestamp: new Date(job.scheduled_at).getTime(),
            action: 'Open Patient',
          });
        }
      });
    });

    // 2. Hardware IoT Dispenser Alerts
    (deviceAlerts?.alerts || []).forEach((alert) => {
      const id = `device-${alert.session_id}`;
      if (!seenIds.has(id)) {
        seenIds.add(id);
        list.push({
          id,
          type: alert.dose_status === 'missed' ? 'critical' : 'warning',
          patient: alert.device_name || 'Smart Dispenser',
          subtitle: `Slot ${alert.compartment_number}`,
          message: `Device reported ${alert.dose_status} for ${alert.time_slot || 'a scheduled dose'}.`,
          time: new Date(alert.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          timestamp: new Date(alert.scheduled_time).getTime(),
          action: 'View Device',
        });
      }
    });

    // 3. In-App Notifications (Missed dose, anomaly, refills)
    (notificationsData?.results || []).forEach((n) => {
      const id = `notif-${n.id}`;
      if (!seenIds.has(id)) {
        seenIds.add(id);
        const isCritical = ['MISSED_DOSE_ALERT', 'DOSE_MISSED', 'CAREGIVER_ALERT', 'ANOMALY_ALERT', 'ALERT'].includes(n.notification_type);
        const isWarning = ['REFILL_ALERT', 'PRESCRIPTION_EXPIRY', 'GEOFENCE_EXIT'].includes(n.notification_type);
        list.push({
          id,
          type: isCritical ? 'critical' : isWarning ? 'warning' : 'info',
          patient: n.title,
          subtitle: n.notification_type?.replace(/_/g, ' '),
          message: n.body || n.message,
          time: n.created_at ? new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--',
          timestamp: n.created_at ? new Date(n.created_at).getTime() : Date.now(),
          action: 'Open Alert',
        });
      }
    });

    return list.sort((left, right) => right.timestamp - left.timestamp);
  }, [alertsQueries, deviceAlerts, notificationsData, patients]);

  const handleAction = (alert) => {
    if (alert.id.startsWith('patient-')) {
      navigate('/caregiver/home');
      return;
    }
    if (alert.id.startsWith('device-')) {
      navigate('/caregiver/compartments');
      return;
    }
    navigate('/notifications');
  };

  const filtered = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return alerts.filter((alert) => {
      const matchesType = filter === 'all' || alert.type === filter;
      const matchesSearch =
        !q ||
        alert.patient?.toLowerCase().includes(q) ||
        alert.message?.toLowerCase().includes(q) ||
        alert.subtitle?.toLowerCase().includes(q);
      return matchesType && matchesSearch;
    });
  }, [alerts, filter, searchTerm]);

  return (
    <div className="flex flex-col gap-8 py-4 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="flex flex-col gap-1">
          <button onClick={() => navigate('/caregiver/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-2">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em]">Dashboard</span>
          </button>
          <h2 className="text-3xl font-display font-extrabold text-foreground tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-destructive/10 flex items-center justify-center">
              <Bell className="w-5 h-5 text-destructive" />
            </div>
            Clinical Alerts Feed
          </h2>
          <p className="text-muted-foreground font-medium">Live alerts from missed doses and dose-session anomalies.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="h-11 px-5 rounded-xl text-xs font-bold uppercase tracking-widest" onClick={handleRefresh} disabled={isRefreshing}>
            <RotateCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Button variant="ghost" className="h-11 px-5 rounded-xl text-xs font-bold uppercase tracking-widest text-muted-foreground" onClick={() => setSearchTerm('')}>
            Clear Filter
          </Button>
        </div>
      </div>

      <Card className="bg-background border-border/40 p-2 rounded-[2rem]">
        <div className="flex flex-col md:flex-row gap-4 p-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground w-5 h-5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter by patient name or alert type..."
              className="w-full pl-12 pr-4 py-3 bg-card border border-border/50 rounded-2xl outline-none focus:ring-2 focus:ring-primary/20 transition-all font-sans font-medium"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {['all', 'critical', 'warning', 'security', 'success'].map((value) => (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={`px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-widest transition-all border ${filter === value ? 'bg-primary text-white border-primary shadow-lg shadow-primary/20' : 'bg-card border-border hover:border-primary/50 text-muted-foreground'}`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <div className="flex flex-col gap-4">
        {isAnyLoading && alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 bg-card rounded-[3rem] border border-border/40 gap-3 animate-pulse">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
            <p className="text-sm font-semibold text-muted-foreground">Fetching clinical alerts stream...</p>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {filtered.map((alert) => (
              <AlertCard key={alert.id} alert={alert} onAction={handleAction} />
            ))}
          </AnimatePresence>
        )}

        {!isAnyLoading && filtered.length === 0 && (
          <div className="text-center py-24 bg-card rounded-[3rem] border border-dashed border-border/60">
            <div className="w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center mx-auto mb-4">
              <ShieldAlert className="w-8 h-8 text-muted-foreground opacity-30" />
            </div>
            <h3 className="text-xl font-display font-bold text-foreground tracking-tight">No alerts found</h3>
            <p className="text-sm text-muted-foreground mt-1 font-medium">
              {searchTerm ? `No alerts match "${searchTerm}". Try clearing the search query.` : 'Everything is currently within clinical parameters.'}
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-center gap-3 opacity-40 mt-8">
        <ShieldAlert className="w-4 h-4" />
        <span className="text-[9px] font-black uppercase tracking-[0.3em]">Live monitoring active</span>
      </div>
    </div>
  );
}
