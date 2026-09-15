import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cpu, ArrowLeft, Wifi, WifiOff, Battery, BatteryLow, Settings2,
  LayoutGrid, AlertTriangle, History, RefreshCw, Loader2, Edit2, X, Check,
  UserPlus, User, ChevronDown, Unlink,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useCaregiverDevices, useDispenserCompartments, useSetupDispenserCompartments, useDeviceStatus, useUpdateDeviceDetail, useLinkPatientToDevice } from '@/hooks/useIoT';
import { useCaregiverPatients } from '@/hooks/useCaregiver';
import { DeviceRegisterPanel } from './device/DeviceRegisterPanel';
import { DispenserGrid } from './device/DispenserGrid';
import { DeviceActionsPanel } from './device/DeviceActionsPanel';
import { useDoseHistory } from '@/hooks/useIoT';

const TABS = [
  { id: 'compartments', label: 'Dispenser', icon: LayoutGrid },
  { id: 'actions',      label: 'Commands & Alerts', icon: AlertTriangle },
  { id: 'history',      label: 'Dose History', icon: History },
];

function StatusBadge({ isOnline }) {
  return isOnline
    ? <Badge variant="success" className="h-5 px-2 text-[10px] font-black uppercase tracking-wider flex items-center gap-1"><Wifi className="w-3 h-3" />Online</Badge>
    : <Badge variant="secondary" className="h-5 px-2 text-[10px] font-black uppercase tracking-wider flex items-center gap-1"><WifiOff className="w-3 h-3" />Offline</Badge>;
}

function HwStatus({ label, value }) {
  const ok = value === 'ok';
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-muted/30">
      <div className={`w-2 h-2 rounded-full ${ok ? 'bg-emerald-500' : 'bg-amber-500'}`} />
      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className={`text-[10px] font-black uppercase ${ok ? 'text-emerald-600' : 'text-amber-600'}`}>{value}</span>
    </div>
  );
}

function PatientPickerDropdown({ deviceId, currentPatientId, onClose }) {
  const { data: patients = [], isLoading } = useCaregiverPatients();
  const linkPatient = useLinkPatientToDevice();

  async function handleSelect(patientId) {
    await linkPatient.mutateAsync({ deviceId, patientId });
    onClose();
  }

  async function handleUnlink() {
    await linkPatient.mutateAsync({ deviceId, patientId: null });
    onClose();
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.97 }}
        className="absolute right-0 top-full mt-2 z-50 bg-card border border-border/60 rounded-2xl shadow-xl w-64 overflow-hidden"
      >
        <div className="px-4 py-3 border-b border-border/40 bg-muted/20">
          <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Select Patient</p>
          <p className="text-xs text-muted-foreground mt-0.5">Device compartments will use this patient's prescriptions.</p>
        </div>
        <div className="py-1 max-h-56 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          )}
          {!isLoading && patients.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4 px-4">No linked patients found.</p>
          )}
          {patients.map(p => {
            const isActive = p.id === currentPatientId;
            return (
              <button
                key={p.id}
                onClick={() => handleSelect(p.id)}
                disabled={linkPatient.isPending}
                className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40 ${isActive ? 'bg-primary/8' : ''}`}
              >
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-sm font-black shrink-0 ${isActive ? 'bg-primary text-white' : 'bg-primary/10 text-primary'}`}>
                  {(p.name || '?')[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-bold truncate ${isActive ? 'text-primary' : 'text-foreground'}`}>{p.name}</p>
                  <p className="text-[10px] text-muted-foreground font-medium">{p.patientCode}</p>
                </div>
                {isActive && <Check className="w-3.5 h-3.5 text-primary shrink-0" />}
              </button>
            );
          })}
        </div>
        {currentPatientId && (
          <div className="border-t border-border/40">
            <button
              onClick={handleUnlink}
              disabled={linkPatient.isPending}
              className="w-full flex items-center gap-2 px-4 py-3 text-destructive hover:bg-destructive/8 transition-colors text-xs font-bold"
            >
              <Unlink className="w-3.5 h-3.5" /> Unlink Patient
            </button>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}

function DeviceHeader({ device, onRefresh, isRefreshing }) {
  const [editing, setEditing] = useState(false);
  const [nameVal, setNameVal] = useState(device.device_name);
  const [showPicker, setShowPicker] = useState(false);
  const updateDevice = useUpdateDeviceDetail();
  const { data: status } = useDeviceStatus(device.id);

  async function saveName() {
    await updateDevice.mutateAsync({ deviceId: device.id, data: { device_name: nameVal } });
    setEditing(false);
  }

  const battery = status?.battery_level ?? device.battery_level;
  const isOnline = status?.is_online ?? device.is_online;
  const linkedName = device.linked_patient_name;
  const linkedId   = device.linked_patient_id;

  return (
    <div className="bg-card rounded-[2rem] border border-border/50 shadow-sm overflow-visible">
      {/* Main row */}
      <div className="p-6 flex flex-col sm:flex-row gap-5 items-start sm:items-center">
        <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center shrink-0">
          <Cpu className="w-7 h-7 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="flex items-center gap-2 mb-2">
              <input autoFocus value={nameVal} onChange={e => setNameVal(e.target.value)}
                className="h-10 px-3 rounded-xl border border-border/80 bg-muted/30 font-bold text-foreground outline-none focus:border-primary/80 text-sm" />
              <button onClick={saveName} className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center hover:bg-emerald-500 hover:text-white transition-all">
                {updateDevice.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              </button>
              <button onClick={() => setEditing(false)} className="w-8 h-8 rounded-lg bg-muted/40 text-muted-foreground flex items-center justify-center hover:bg-muted transition-all"><X className="w-3.5 h-3.5" /></button>
            </div>
          ) : (
            <div className="flex items-center gap-2 mb-1">
              <h2 className="font-display font-extrabold text-xl text-foreground truncate">{device.device_name}</h2>
              <button onClick={() => setEditing(true)} className="w-6 h-6 rounded-md bg-muted/40 text-muted-foreground flex items-center justify-center hover:bg-muted transition-all"><Edit2 className="w-3 h-3" /></button>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge isOnline={isOnline} />
            {battery != null && (
              <div className="flex items-center gap-1 text-[10px] font-bold text-muted-foreground">
                {battery < 20 ? <BatteryLow className="w-3.5 h-3.5 text-destructive" /> : <Battery className="w-3.5 h-3.5" />}
                {battery}%
              </div>
            )}
            <span className="text-[10px] text-muted-foreground font-medium">{device.firmware_version || 'firmware unknown'}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap mt-2">
            <HwStatus label="Stepper" value={status?.stepper_status ?? device.stepper_status ?? 'ok'} />
            <HwStatus label="Servo" value={status?.servo_status ?? device.servo_status ?? 'ok'} />
            <HwStatus label="Sensor" value={status?.ultrasonic_status ?? device.ultrasonic_status ?? 'ok'} />
          </div>
        </div>
        <button onClick={onRefresh} disabled={isRefreshing}
          className="w-9 h-9 rounded-xl bg-muted/40 text-muted-foreground flex items-center justify-center hover:bg-muted transition-all shrink-0">
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Patient linkage strip */}
      <div className="px-6 pb-5 relative">
        <div className={`flex items-center justify-between gap-4 px-4 py-3 rounded-2xl border ${linkedName ? 'bg-primary/5 border-primary/20' : 'bg-muted/20 border-dashed border-border/60'}`}>
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${linkedName ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'}`}>
              <User className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground">Linked Patient</p>
              {linkedName ? (
                <p className="text-sm font-bold text-foreground truncate">{linkedName}
                  <span className="ml-2 text-[10px] font-medium text-muted-foreground">{device.linked_patient_code}</span>
                </p>
              ) : (
                <p className="text-xs text-muted-foreground font-medium">No patient linked — compartments inactive</p>
              )}
            </div>
          </div>

          <div className="relative shrink-0">
            <button
              onClick={() => setShowPicker(v => !v)}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all border ${
                linkedName
                  ? 'bg-card border-border/50 text-foreground hover:border-primary/40 hover:text-primary'
                  : 'bg-primary text-white border-primary shadow-md shadow-primary/20 hover:bg-primary/90'
              }`}
            >
              <UserPlus className="w-3.5 h-3.5" />
              {linkedName ? 'Change' : 'Link Patient'}
              <ChevronDown className={`w-3 h-3 transition-transform ${showPicker ? 'rotate-180' : ''}`} />
            </button>

            {showPicker && (
              <PatientPickerDropdown
                deviceId={device.id}
                currentPatientId={linkedId}
                onClose={() => setShowPicker(false)}
              />
            )}
          </div>
        </div>

        {linkedName && (
          <p className="text-[10px] text-muted-foreground font-medium mt-2 px-1">
            Compartment schedules and dose tracking are scoped to <span className="font-bold text-foreground">{linkedName}</span>'s prescriptions.
          </p>
        )}
      </div>
    </div>
  );
}

function DoseHistoryTab({ deviceId }) {
  const { data: sessions = [], isLoading } = useDoseHistory(deviceId);
  if (isLoading) return <div className="text-sm text-muted-foreground p-6 text-center font-medium">Loading history...</div>;
  if (!sessions.length) return <div className="text-sm text-muted-foreground p-6 text-center font-medium">No dose sessions recorded yet.</div>;
  const STATUS_COLOR = { taken: 'success', missed: 'destructive', partial: 'warning', pending: 'secondary' };
  return (
    <div className="bg-card rounded-[2rem] border border-border/50 overflow-hidden">
      <div className="p-6 border-b border-border/40 bg-muted/10">
        <h3 className="font-display font-bold text-lg">Dose History</h3>
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-widest mt-0.5">{sessions.length} session{sessions.length !== 1 ? 's' : ''}</p>
      </div>
      <div className="divide-y divide-border/40 max-h-[500px] overflow-y-auto">
        {sessions.map(s => (
          <div key={s.id} className="flex items-center gap-4 px-6 py-4 hover:bg-muted/10 transition-colors">
            <div className="w-9 h-9 rounded-xl bg-muted/40 flex items-center justify-center shrink-0 font-black text-sm text-foreground">{s.compartment_number}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-foreground">{s.time_slot?.replace(/_/g, ' ')}</p>
              <p className="text-[10px] text-muted-foreground font-medium">{s.scheduled_time ? new Date(s.scheduled_time).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}</p>
            </div>
            {s.weight_reduction_actual != null && (
              <p className="text-[10px] text-muted-foreground font-medium shrink-0">{s.weight_reduction_actual?.toFixed(1)}g</p>
            )}
            <Badge variant={STATUS_COLOR[s.dose_status] || 'secondary'} className="h-5 px-2 text-[9px] font-black uppercase shrink-0">{s.dose_status}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DeviceManager() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('compartments');
  const { data: devices = [], isLoading, isError, refetch } = useCaregiverDevices();

  const device = devices[0] ?? null;
  const { data: compartments = [], isLoading: loadingCompartments, refetch: refetchCompartments } = useDispenserCompartments(device?.id);
  const setupCompartments = useSetupDispenserCompartments();

  async function handleSetup() {
    await setupCompartments.mutateAsync(device.id);
    refetchCompartments();
  }

  function handleRefresh() { refetch(); }
  function handleDeviceRegistered() { refetch(); }

  return (
    <div className="flex flex-col gap-8 py-4 max-w-[1600px] mx-auto w-full">
      {/* Page header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <button onClick={() => navigate('/caregiver/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-2">
            <ArrowLeft className="w-4 h-4" /><span className="text-[10px] font-black uppercase tracking-[0.2em]">Dashboard</span>
          </button>
          <h1 className="font-display font-extrabold text-3xl tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center"><Cpu className="w-5 h-5 text-primary" /></div>
            IoT Device Manager
          </h1>
          <p className="text-muted-foreground font-medium mt-1">Register, configure, and control your MedAdhere smart dispenser.</p>
        </div>
        {device && (
          <Button variant="outline" className="h-11 px-5 rounded-xl font-bold border-border/60 hover:border-primary/30"
            onClick={() => navigate('/caregiver/settings')}>
            <Settings2 className="w-4 h-4 mr-2" />Device Settings
          </Button>
        )}
      </div>

      {/* Loading */}
      {isLoading && <div className="flex items-center justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>}

      {/* API error — don't show register panel, show retry */}
      {!isLoading && isError && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <p className="text-muted-foreground font-medium">Could not load device data. Check your connection.</p>
          <Button variant="outline" onClick={refetch} className="h-10 px-5 rounded-xl font-bold">
            <RefreshCw className="w-4 h-4 mr-2" />Retry
          </Button>
        </div>
      )}

      {/* No device — show registration flow */}
      {!isLoading && !isError && !device && <DeviceRegisterPanel onSuccess={handleDeviceRegistered} />}

      {/* Has device — show full manager */}
      {!isLoading && !isError && device && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          <DeviceHeader device={device} onRefresh={handleRefresh} isRefreshing={false} />

          {/* Tabs */}
          <div className="flex gap-1 bg-muted/50 p-1.5 rounded-2xl w-fit">
            {TABS.map(t => {
              const Icon = t.icon;
              const active = tab === t.id;
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${active ? 'bg-card text-primary shadow-sm border border-border/40' : 'text-muted-foreground hover:text-foreground'}`}>
                  <Icon className="w-4 h-4" />{t.label}
                </button>
              );
            })}
          </div>

          {/* Tab content */}
          {tab === 'compartments' && (
            <>
              {loadingCompartments && <div className="text-sm text-muted-foreground p-6 text-center font-medium">Loading compartments...</div>}
              {!loadingCompartments && compartments.length === 0 && (
                <div className="p-10 bg-card rounded-[2rem] border border-dashed border-border/60 text-center flex flex-col items-center gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                    <LayoutGrid className="w-7 h-7 text-primary" />
                  </div>
                  <div>
                    <p className="font-bold text-foreground mb-1">Dispenser not initialised</p>
                    <p className="text-sm text-muted-foreground font-medium">Click below to create the 4 time-slot compartments on this device.</p>
                  </div>
                  <Button
                    className="h-11 px-8 rounded-xl font-bold shadow-md shadow-primary/20"
                    onClick={handleSetup}
                    disabled={setupCompartments.isPending}
                  >
                    {setupCompartments.isPending
                      ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Setting up...</>
                      : 'Setup Dispenser Compartments'}
                  </Button>
                </div>
              )}
              {!loadingCompartments && compartments.length > 0 && <DispenserGrid deviceId={device.id} compartments={compartments} />}
            </>
          )}

          {tab === 'actions' && <DeviceActionsPanel deviceId={device.id} />}
          {tab === 'history' && <DoseHistoryTab deviceId={device.id} />}
        </motion.div>
      )}
    </div>
  );
}
