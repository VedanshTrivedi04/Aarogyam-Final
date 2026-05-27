import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Pill, RotateCw, Edit2, X, Info, Clock, LayoutGrid, Weight,
  ArrowLeft, ShieldCheck, Loader2, CheckCircle2, AlertCircle
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  useCaregiverDevices, useDeviceInventory, useDeviceCompartments,
  useUpdateDeviceCompartments, useDispenserCompartments,
  useUpdateCompartmentSlotTime,
} from '@/hooks/useIoT';
import { useRescheduleCompartment } from '@/hooks/useCaregiver';
import { useUiStore } from '@/stores/ui.store';

const SLOT_LABELS = {
  morning_before: 'Morning · Before Food',
  morning_after:  'Morning · After Food',
  night_before:   'Night · Before Food',
  night_after:    'Night · After Food',
};

function fmt12h(time24) {
  if (!time24) return '—';
  const [h, m] = time24.split(':').map(Number);
  const suffix = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, '0')} ${suffix}`;
}

const CompartmentCard = ({ comp, onEdit }) => (
  <Card className={`group rounded-[2.5rem] border-2 transition-all hover:shadow-elevation-3 ${comp.is_active || comp.is_filled ? 'border-transparent bg-card' : 'border-dashed border-border/60 bg-muted/20'}`}>
    <CardContent className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div className="flex items-center gap-4">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-xl font-black shadow-lg ${comp.is_active || comp.is_filled ? 'bg-primary text-white shadow-primary/20' : 'bg-muted text-muted-foreground'}`}>
            {comp.compartment_number}
          </div>
          <div>
            <h3 className="font-display font-bold text-lg text-foreground">Slot {comp.compartment_number}</h3>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-widest">
              {SLOT_LABELS[comp.time_slot] || comp.time_slot_display || comp.medication_name || 'Unassigned'}
            </p>
          </div>
        </div>
        <Badge variant={comp.is_active || comp.is_filled ? 'success' : 'secondary'} className="h-6 px-3 rounded-full text-[9px] font-black uppercase tracking-wider">
          {comp.is_active ? 'active' : comp.is_filled ? 'filled' : 'empty'}
        </Badge>
      </div>

      <div className="space-y-3 min-h-[100px]">
        {/* Alarm time — primary field */}
        <div className="flex items-center gap-3 p-3 bg-primary/8 border border-primary/20 rounded-xl">
          <Clock className="w-4 h-4 text-primary shrink-0" />
          <div className="flex-1">
            <p className="text-[10px] font-black uppercase tracking-widest text-primary/70">Alarm Time</p>
            <p className="text-sm font-black text-primary">{fmt12h(comp.scheduled_time)}</p>
          </div>
        </div>

        {/* Medicine list */}
        <div className="flex items-center gap-3 p-3 bg-muted/40 rounded-xl">
          <Pill className="w-4 h-4 text-primary shrink-0" />
          <div>
            <p className="text-xs font-bold text-foreground">
              {comp.sub_compartments?.length
                ? comp.sub_compartments.map((s) => s.medicine_name).join(', ')
                : comp.medication_name || 'No medicine added'}
            </p>
            <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-tighter">
              {comp.total_medicines != null ? `${comp.total_medicines} medicine(s)` : `Qty: ${comp.total_pills ?? 0}`}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 pt-5 border-t border-border/40 flex items-center justify-between">
        <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2">
          <Weight className="w-3.5 h-3.5" />
          {comp.current_balance_weight_grams != null
            ? `${comp.current_balance_weight_grams}g balance`
            : `Pills: ${comp.pills_remaining ?? 0}`}
        </div>
        <button
          onClick={() => onEdit(comp)}
          className="w-10 h-10 rounded-xl bg-secondary text-primary flex items-center justify-center hover:bg-primary hover:text-white transition-all shadow-sm"
        >
          <Edit2 className="w-4 h-4" />
        </button>
      </div>
    </CardContent>
  </Card>
);

export default function CompartmentManager() {
  const navigate = useNavigate();
  const { data: devices = [], isLoading: isLoadingDevices } = useCaregiverDevices();
  const activeDevice = devices[0];
  const deviceId = activeDevice?.id;

  // New dispenser system (PhysicalCompartment with scheduled_time)
  const { data: dispenserComps = [], isLoading: isLoadingDispenser } = useDispenserCompartments(deviceId);
  // Legacy fallback
  const { data: inventory } = useDeviceInventory(deviceId);
  const { data: legacyComps = [], isLoading: isLoadingLegacy } = useDeviceCompartments(deviceId);

  const updateCompartments = useUpdateDeviceCompartments();
  const updateSlotTime = useUpdateCompartmentSlotTime();
  const reschedule = useRescheduleCompartment();
  const activePatientId = useUiStore((s) => s.activePatientId);

  // Prefer new dispenser compartments
  const liveCompartments = useMemo(() => {
    if (dispenserComps.length > 0) return dispenserComps;
    const source = legacyComps.length ? legacyComps : inventory?.compartments || [];
    return source.map((comp) => ({
      ...comp,
      compartment_number: comp.compartment_number ?? comp.compartment,
      medication_name: comp.medication_name ?? comp.medication_name_display,
      is_filled: typeof comp.is_filled === 'boolean' ? comp.is_filled : (comp.pills_remaining ?? 0) > 0,
    }));
  }, [dispenserComps, legacyComps, inventory]);

  const useNewSystem = dispenserComps.length > 0;

  const [editingComp, setEditingComp] = useState(null);
  const [formState, setFormState] = useState({
    medication_name: '', priority: 'NORMAL', meal_dependency: 'NONE',
    scheduled_times: '', total_pills: 0, scheduled_time: '08:00',
  });
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState('');

  const openEditor = (comp) => {
    setEditingComp(comp);
    setSaveSuccess(false);
    setSaveError('');
    setFormState({
      medication_name: comp.medication_name || comp.medication_name_display || '',
      priority: comp.priority || 'NORMAL',
      meal_dependency: comp.meal_dependency || 'NONE',
      scheduled_times: Array.isArray(comp.scheduled_times) ? comp.scheduled_times.join(', ') : '',
      total_pills: comp.total_pills ?? 0,
      prescription: comp.prescription || '',
      scheduled_time: comp.scheduled_time || '08:00',
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!activeDevice || !editingComp) return;
    setSaveSuccess(false);
    setSaveError('');

    try {
      if (useNewSystem) {
        // New system: PATCH /dispenser/compartments/{num}/time/
        await updateSlotTime.mutateAsync({
          deviceId: activeDevice.id,
          compartmentNum: editingComp.compartment_number,
          scheduledTime: formState.scheduled_time,
        });
      } else {
        // Legacy system
        const updated = liveCompartments.map((comp) => {
          if (String(comp.compartment_number) !== String(editingComp.compartment_number)) {
            return {
              compartment_number: comp.compartment_number,
              prescription: comp.prescription,
              scheduled_times: comp.scheduled_times || [],
              priority: comp.priority || 'NORMAL',
              meal_dependency: comp.meal_dependency || 'NONE',
              medication_name: comp.medication_name || comp.medication_name_display || '',
              total_pills: comp.total_pills ?? 0,
            };
          }
          return {
            compartment_number: comp.compartment_number,
            prescription: editingComp.prescription || comp.prescription,
            scheduled_times: formState.scheduled_times.split(',').map((t) => t.trim()).filter(Boolean),
            priority: formState.priority,
            meal_dependency: formState.meal_dependency,
            medication_name: formState.medication_name,
            total_pills: Number(formState.total_pills || 0),
          };
        });
        await updateCompartments.mutateAsync({ deviceId: activeDevice.id, compartments: updated });
        const newTimes = formState.scheduled_times.split(',').map((t) => t.trim()).filter(Boolean);
        if (activePatientId && newTimes.length > 0) {
          try {
            await reschedule.mutateAsync({
              patientId: activePatientId, deviceId: activeDevice.id,
              compartmentNumber: editingComp.compartment_number, payload: { times: newTimes },
            });
          } catch (err) { console.error('Reschedule failed', err); }
        }
      }

      setSaveSuccess(true);
      setTimeout(() => setEditingComp(null), 1200);
    } catch (err) {
      setSaveError(err?.response?.data?.error?.message || 'Failed to update. Please try again.');
    }
  };

  const isLoading = isLoadingDevices || isLoadingDispenser || isLoadingLegacy;
  const totalWeight = inventory?.compartments?.reduce((sum, c) => sum + (c.pills_remaining || 0), 0) ?? 0;
  const filledCount = inventory?.filled_count ?? liveCompartments.filter((c) => c.is_active || c.is_filled).length;
  const totalCompartments = inventory?.total_compartments ?? liveCompartments.length;
  const isPending = updateSlotTime.isPending || updateCompartments.isPending;

  return (
    <div className="flex flex-col gap-8 py-4">

      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="flex flex-col gap-1">
          <button onClick={() => navigate('/caregiver/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-2">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em]">Dashboard</span>
          </button>
          <h2 className="text-3xl font-display font-extrabold text-foreground tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <LayoutGrid className="w-5 h-5 text-primary" />
            </div>
            Device Logic Manager
          </h2>
          <p className="text-muted-foreground font-medium">
            Manage compartments &amp; alarm times for {activeDevice?.device_name || 'your linked dispenser'}.
          </p>
        </div>
        <Button onClick={() => navigate('/caregiver/fill')} className="h-12 px-8 rounded-xl shadow-lg shadow-primary/20 font-black uppercase tracking-widest text-xs" disabled={!activeDevice}>
          <RotateCw className="w-4 h-4 mr-2" /> Sync with OLED
        </Button>
      </div>

      {/* Compartment grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {isLoading ? (
          <div className="lg:col-span-4 text-sm text-muted-foreground p-6 bg-card rounded-2xl border border-border/50">Loading device compartments…</div>
        ) : liveCompartments.length === 0 ? (
          <div className="lg:col-span-4 p-8 bg-card rounded-2xl border border-dashed border-border/60 text-center text-muted-foreground">
            <LayoutGrid className="w-8 h-8 mx-auto mb-3 opacity-40" />
            <p className="font-bold">No compartments found.</p>
            <p className="text-xs mt-1">Run dispenser setup from device settings.</p>
          </div>
        ) : liveCompartments.map((comp) => (
          <CompartmentCard key={comp.compartment_number} comp={comp} onEdit={openEditor} />
        ))}
      </div>

      {/* Diagnostics row */}
      <div className="grid lg:grid-cols-3 gap-8">
        <Card className="lg:col-span-2 rounded-[2.5rem]">
          <CardHeader className="border-b border-border/40 p-8 flex flex-row items-center justify-between bg-muted/10">
            <div>
              <h3 className="font-display font-bold text-xl">System Diagnostics</h3>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-widest mt-1">Live device and inventory data</p>
            </div>
            <Badge variant={activeDevice?.is_online ? 'success' : 'warning'} className="h-6 px-3 rounded-full text-[9px] font-black uppercase tracking-widest">
              {activeDevice?.is_online ? 'Connected' : 'Offline'}
            </Badge>
          </CardHeader>
          <CardContent className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                { label: 'Total Pills', value: String(totalWeight), sub: 'Across compartments', icon: Weight },
                { label: 'Active Slots', value: `${filledCount}/${totalCompartments}`, sub: 'Loaded compartments', icon: RotateCw },
                { label: 'Gate Security', value: activeDevice?.is_gate_locked ? 'Locked' : 'Unlocked', sub: 'Current lock state', icon: ShieldCheck },
              ].map((diag) => (
                <div key={diag.label} className="flex items-center gap-4 p-5 bg-card border border-border/50 rounded-2xl shadow-sm">
                  <div className="w-12 h-12 rounded-xl bg-secondary flex items-center justify-center text-primary shrink-0">
                    <diag.icon className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">{diag.label}</p>
                    <p className="text-xl font-black text-foreground">{diag.value}</p>
                    <p className="text-[10px] text-primary font-bold uppercase tracking-tighter">{diag.sub}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[2.5rem] bg-primary/5 border-primary/20 border-dashed">
          <CardContent className="p-8 flex flex-col items-center text-center gap-5 h-full justify-center">
            <div className="w-16 h-16 rounded-3xl bg-white flex items-center justify-center shadow-xl">
              <Info className="w-8 h-8 text-primary" />
            </div>
            <h4 className="font-display font-bold text-lg">How Alarm Times Work</h4>
            <p className="text-xs text-muted-foreground font-medium leading-relaxed">
              Each compartment has its own alarm time. The ESP32 dispenser opens the correct slot within <strong>±10 minutes</strong> of that time. Click <strong>Edit</strong> on any slot to change it anytime.
            </p>
            <Button variant="outline" className="w-full h-11 rounded-xl border-primary/20 text-primary font-bold text-xs uppercase tracking-widest" onClick={() => navigate('/caregiver/settings')}>
              Open Settings
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Edit modal */}
      <AnimatePresence>
        {editingComp && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/60 backdrop-blur-md" onClick={() => setEditingComp(null)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="bg-card w-full max-w-lg rounded-[3rem] shadow-2xl relative z-10 overflow-hidden border border-border/50"
            >
              {/* Modal header */}
              <div className="p-8 border-b border-border/40 flex justify-between items-center bg-primary text-white">
                <div>
                  <h2 className="text-2xl font-display font-extrabold tracking-tight">
                    Compartment {editingComp.compartment_number}
                  </h2>
                  <p className="text-[10px] font-black uppercase tracking-widest opacity-70">
                    {SLOT_LABELS[editingComp.time_slot] || 'Update alarm time'}
                  </p>
                </div>
                <button onClick={() => setEditingComp(null)} className="p-3 hover:bg-white/10 rounded-2xl transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>

              <form onSubmit={handleSave} className="p-8 flex flex-col gap-5">
                {/* Alarm time — primary */}
                <div className="p-5 rounded-2xl border-2 border-primary/25 bg-primary/5">
                  <label className="flex flex-col gap-3">
                    <span className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                      <Clock className="w-4 h-4" /> Alarm Time (24h)
                    </span>
                    <input
                      type="time"
                      value={formState.scheduled_time}
                      onChange={(e) => setFormState((s) => ({ ...s, scheduled_time: e.target.value }))}
                      className="w-full rounded-xl border-2 border-primary/30 bg-background px-4 py-3 text-xl font-black text-primary focus:outline-none focus:border-primary transition-colors"
                      required
                    />
                    <p className="text-[10px] text-muted-foreground">
                      ESP32 will dispense from this slot within <strong>±10 min</strong> of this time.
                    </p>
                  </label>
                </div>

                {/* Legacy fields — only show when NOT using new dispenser system */}
                {!useNewSystem && (
                  <>
                    <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      Medicine Name
                      <input value={formState.medication_name} onChange={(e) => setFormState((s) => ({ ...s, medication_name: e.target.value }))} className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3" />
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                        Quantity
                        <input type="number" value={formState.total_pills} onChange={(e) => setFormState((s) => ({ ...s, total_pills: e.target.value }))} className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3" />
                      </label>
                      <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                        Priority
                        <select value={formState.priority} onChange={(e) => setFormState((s) => ({ ...s, priority: e.target.value }))} className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3">
                          <option value="NORMAL">Normal</option>
                          <option value="HIGH">High</option>
                        </select>
                      </label>
                    </div>
                    <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      Scheduled Times (comma-separated)
                      <input value={formState.scheduled_times} onChange={(e) => setFormState((s) => ({ ...s, scheduled_times: e.target.value }))} placeholder="08:00, 20:00" className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3" />
                    </label>
                  </>
                )}

                {/* Status */}
                {saveSuccess && (
                  <div className="flex items-center gap-3 p-4 bg-green-500/10 border border-green-500/30 rounded-2xl text-green-600">
                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                    <p className="text-sm font-bold">Time updated! Device will sync on next poll.</p>
                  </div>
                )}
                {saveError && (
                  <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-2xl text-destructive">
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <p className="text-sm font-bold">{saveError}</p>
                  </div>
                )}

                <div className="flex gap-4 mt-1">
                  <Button variant="outline" type="button" className="flex-1 h-14 rounded-2xl font-bold uppercase tracking-widest text-xs" onClick={() => setEditingComp(null)}>
                    Cancel
                  </Button>
                  <Button type="submit" className="flex-1 h-14 rounded-2xl font-bold uppercase tracking-widest text-xs shadow-lg shadow-primary/20" disabled={isPending}>
                    {isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Clock className="w-4 h-4 mr-2" />}
                    {isPending ? 'Saving…' : 'Update Time'}
                  </Button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
