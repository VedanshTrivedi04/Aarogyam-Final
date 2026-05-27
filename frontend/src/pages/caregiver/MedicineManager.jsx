import { useState, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Pill, Plus, X, ArrowLeft, Clock, Loader2,
  AlertCircle, Cpu, User, CheckCircle2, Sun, Moon, Utensils, Trash2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useCaregiverPatients, useCaregiverPatientPrescriptions, useCreateCaregiverPrescription, useDeleteCaregiverPrescription, useCaregiverPatientDevices, useRescheduleCompartment } from '@/hooks/useCaregiver';
import { useDispenserCompartments } from '@/hooks/useIoT';

// ── Shared slot metadata (same as DispenserGrid) ─────────────────────────────

const SLOT_META = {
  1: { key: 'morning_before', label: 'Morning — Before Food', icon: Sun,  time: '08:00', with_food: false, color: 'text-amber-500',  bg: 'bg-amber-500/10',  border: 'border-amber-200' },
  2: { key: 'morning_after',  label: 'Morning — After Food',  icon: Sun,  time: '09:00', with_food: true,  color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-200' },
  3: { key: 'night_before',   label: 'Night — Before Food',   icon: Moon, time: '20:00', with_food: false, color: 'text-violet-500', bg: 'bg-violet-500/10', border: 'border-violet-200' },
  4: { key: 'night_after',    label: 'Night — After Food',    icon: Moon, time: '21:00', with_food: true,  color: 'text-indigo-500', bg: 'bg-indigo-500/10', border: 'border-indigo-200' },
};

const DURATION_OPTIONS = [
  { label: '7 Days',  value: 7 },
  { label: '14 Days', value: 14 },
  { label: '21 Days', value: 21 },
  { label: '30 Days', value: 30 },
  { label: 'Indefinite', value: null },
];

// ── Patient tab ───────────────────────────────────────────────────────────────

function PatientTab({ patient, isActive, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 px-5 py-3 rounded-2xl font-bold text-sm transition-all whitespace-nowrap ${
        isActive
          ? 'bg-primary text-white shadow-lg shadow-primary/20'
          : 'bg-card text-muted-foreground hover:bg-secondary hover:text-foreground border border-border/50'
      }`}
    >
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-sm font-black shrink-0 ${isActive ? 'bg-white/20' : 'bg-primary/10 text-primary'}`}>
        {(patient.name || '?')[0].toUpperCase()}
      </div>
      {patient.name.split(' ')[0]}
    </button>
  );
}

// ── Compartment slot card ─────────────────────────────────────────────────────

function CompartmentSlot({ slot, prescriptions: rxList = [], onAddClick, onEditClick }) {
  const meta  = SLOT_META[slot.compartment_number] ?? SLOT_META[1];
  const Icon  = meta.icon;
  const activeSubs = (slot.sub_compartments || []).filter(sub => sub.is_active !== false);
  const activeRx = rxList.filter(rx => rx.is_active !== false);
  const medicines = activeSubs.length ? activeSubs : activeRx;
  const isEmpty = medicines.length === 0 && !slot.medication_name;
  let displayTime = meta.time;
  if (slot && slot.scheduled_times && slot.scheduled_times.length > 0) {
    displayTime = Array.isArray(slot.scheduled_times) ? slot.scheduled_times.join(', ') : String(slot.scheduled_times);
  } else if (rxList && rxList.length > 0) {
    const rxTimes = rxList[0].schedules?.[0]?.times_of_day ?? [];
    if (rxTimes.length > 0) {
      displayTime = rxTimes.map(t => t.time).join(', ');
    }
  }

  return (
    <Card className={`rounded-[2rem] border-2 transition-all hover:shadow-elevation-2 overflow-hidden ${isEmpty ? 'border-dashed border-border/50' : 'border-transparent'}`}>
      {/* Slot header */}
      <div className={`px-5 pt-5 pb-3 flex items-center gap-3 ${meta.bg}`}>
        <div className={`w-10 h-10 rounded-xl ${meta.bg} flex items-center justify-center shrink-0`}>
          <Icon className={`w-5 h-5 ${meta.color}`} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground">Slot {slot.compartment_number}</p>
          <p className="text-sm font-bold text-foreground truncate">{meta.label}</p>
          <p className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
            <Clock className="w-3 h-3" />{displayTime}
            <span className="mx-1">·</span>
            <Utensils className="w-3 h-3" />{meta.with_food ? 'After food' : 'Before food'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {medicines.length > 0 && (
            <span className="shrink-0 text-[9px] font-black uppercase tracking-wider bg-primary/10 text-primary px-2 py-0.5 rounded-full">
              {medicines.length} med{medicines.length > 1 ? 's' : ''}
            </span>
          )}
          {(slot.medication_name || medicines.length > 0 || (slot.scheduled_times && slot.scheduled_times.length > 0)) && (
            <button type="button" onClick={() => onEditClick(slot)} className="w-8 h-8 rounded-xl bg-secondary text-primary flex items-center justify-center hover:bg-primary hover:text-white transition-all shadow-sm">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5h6M4 7v10a2 2 0 002 2h10M7 7v10m0 0L17 7" /></svg>
            </button>
          )}
        </div>
      </div>

      <CardContent className="p-4 space-y-2">
        {isEmpty ? (
          <p className="text-xs text-muted-foreground font-medium text-center py-2">No medicine assigned</p>
        ) : (
          <div className="space-y-1.5">
            {medicines.map(med => (
              <div key={med.id} className="flex items-start gap-2 p-2 rounded-xl bg-muted/30">
                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-foreground truncate">{med.medicine_name ?? med.medication?.name}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {med.quantity_per_dose != null ? `${med.quantity_per_dose}×` : `${med.dosage_value ?? ''}${med.dosage_unit ?? ''}`}
                    {med.duration_days ? ` · ${med.duration_days}d` : ''}
                    {med.total_pills != null ? ` · ${med.total_pills} pills` : ''}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
        {/* Always show Add button */}
        <button
          onClick={() => onAddClick(slot.compartment_number)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-primary/10 text-primary hover:bg-primary hover:text-white transition-all text-[10px] font-black uppercase tracking-wider mt-1"
        >
          <Plus className="w-3 h-3" /> Add Medicine
        </button>
      </CardContent>
    </Card>
  );
}

// ── Active prescription row ───────────────────────────────────────────────────

function PrescriptionRow({ rx, patientId }) {
  const times = rx.schedules?.[0]?.times_of_day ?? [];
  const slotNum = rx.compartment_number ?? (
    Object.values(SLOT_META).find(m => times.some(t => t.time === m.time))
      ? Number(Object.keys(SLOT_META).find(k => times.some(t => t.time === SLOT_META[k].time)))
      : null
  );
  const meta = slotNum ? SLOT_META[slotNum] : null;
  const formattedTimes = times.map(t => t.time).join(', ');

  const deleteMutation = useDeleteCaregiverPrescription();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    try {
      await deleteMutation.mutateAsync({ patientId, prescriptionId: rx.id });
      setConfirmDelete(false);
    } catch (error) {
      console.error('Delete failed:', error);
      setConfirmDelete(false);
    }
  };

  return (
    <div className="flex items-center gap-4 p-4 rounded-2xl bg-muted/30 hover:bg-muted/50 transition-colors group">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${meta ? meta.bg : 'bg-primary/10'}`}>
        {meta ? <meta.icon className={`w-5 h-5 ${meta.color}`} /> : <Pill className="w-5 h-5 text-primary" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-sm text-foreground truncate">{rx.medication?.name ?? '—'}</p>
        <p className="text-xs text-muted-foreground">
          {rx.dosage_value}{rx.dosage_unit}
          {meta && ` · ${meta.label}`}
          {formattedTimes && ` at ${formattedTimes}`}
          {rx.end_date && ` · until ${new Date(rx.end_date).toLocaleDateString()}`}
          {rx.is_indefinite && ' · ongoing'}
        </p>
      </div>
      <Badge variant={rx.is_active ? 'success' : 'secondary'} className="text-[9px] font-black uppercase tracking-wider px-2 h-5 rounded-full shrink-0">
        {rx.is_active ? 'active' : 'paused'}
      </Badge>
      <button
        onClick={handleDelete}
        disabled={deleteMutation.isPending}
        className={`shrink-0 p-2 rounded-lg transition-all opacity-0 group-hover:opacity-100 ${
          confirmDelete
            ? 'bg-destructive/20 text-destructive hover:bg-destructive hover:text-white'
            : 'text-muted-foreground hover:bg-destructive/20 hover:text-destructive'
        }`}
        title={confirmDelete ? 'Click again to confirm deletion' : 'Delete medicine'}
      >
        {deleteMutation.isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Trash2 className="w-4 h-4" />
        )}
      </button>
    </div>
  );
}

// ── Add Medicine Modal — same form logic as DispenserGrid ─────────────────────

const DOCTOR_NAMES_KEY = 'aarogyam:doctor_names';

function loadDoctorNames() {
  try { return JSON.parse(localStorage.getItem(DOCTOR_NAMES_KEY)) ?? []; }
  catch { return []; }
}

function saveDoctorName(name) {
  const trimmed = name.trim();
  if (!trimmed) return;
  const existing = loadDoctorNames();
  if (existing.some(n => n.toLowerCase() === trimmed.toLowerCase())) return;
  localStorage.setItem(DOCTOR_NAMES_KEY, JSON.stringify([trimmed, ...existing].slice(0, 20)));
}

function DoctorAutocomplete({ value, onChange }) {
  const [open, setOpen]           = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const wrapperRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function handleChange(e) {
    const val = e.target.value;
    onChange(val);
    const all = loadDoctorNames();
    const filtered = val.trim()
      ? all.filter(n => n.toLowerCase().includes(val.toLowerCase()))
      : all;
    setSuggestions(filtered);
    setOpen(filtered.length > 0);
  }

  function handleFocus() {
    const all = loadDoctorNames();
    const filtered = value.trim()
      ? all.filter(n => n.toLowerCase().includes(value.toLowerCase()))
      : all;
    if (filtered.length > 0) { setSuggestions(filtered); setOpen(true); }
  }

  function pick(name) {
    onChange(name);
    setOpen(false);
  }

  return (
    <div ref={wrapperRef} className="relative mt-2">
      <input
        value={value}
        onChange={handleChange}
        onFocus={handleFocus}
        placeholder="e.g. Dr. Sharma"
        autoComplete="off"
        className="w-full h-12 px-4 rounded-xl border border-border/80 bg-muted/30 outline-none font-semibold text-foreground focus:border-primary/80 text-sm"
      />
      {open && (
        <ul className="absolute z-50 left-0 right-0 top-[calc(100%+4px)] bg-card border border-border rounded-xl shadow-elevation-2 overflow-hidden max-h-44 overflow-y-auto">
          {suggestions.map(name => (
            <li key={name}>
              <button
                type="button"
                onMouseDown={() => pick(name)}
                className="w-full text-left px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-secondary hover:text-primary transition-colors"
              >
                {name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AddMedicineModal({ patientId, deviceId, compartmentNumber, onClose, onSuccess }) {
  const meta = SLOT_META[compartmentNumber] ?? SLOT_META[1];
  const Icon = meta.icon;

  const [form, setForm] = useState({
    medicine_name: '',
    doctor_name: '',
    quantity_per_dose: 1,
    duration_days: 7,
    total_pills: 7,
    instructions: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const createRx    = useCreateCaregiverPrescription();

  const isPending = createRx.isPending;

  function set(k, v) {
    setForm(f => ({ ...f, [k]: v }));
    setError('');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.medicine_name.trim()) return setError('Medicine name is required.');
    if (!form.quantity_per_dose || form.quantity_per_dose < 1) return setError('Quantity per dose must be at least 1.');

    try {
      // 1. Create prescription + schedule on patient side and sync to linked IoT device
      await createRx.mutateAsync({
        patientId,
        payload: {
          medicine_name:      form.medicine_name.trim(),
          medicine_form:      'TABLET',
          prescribed_by:      form.doctor_name.trim() || undefined,
          dosage_value:       Number(form.quantity_per_dose),
          dosage_unit:        'tablet(s)',
          total_pills:        Number(form.total_pills),
          compartment_number: compartmentNumber,
          duration_days:      form.duration_days,
          schedule_times: [{
            time:      meta.time,
            label:     meta.label,
            with_food: meta.with_food,
          }],
          instructions: form.instructions || undefined,
        },
      });

      if (form.doctor_name.trim()) saveDoctorName(form.doctor_name.trim());
      setSuccess(true);
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Failed to save. Please try again.');
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/60 backdrop-blur-md"
        onClick={!isPending ? onClose : undefined}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="relative z-10 w-full max-w-md bg-card rounded-[2rem] border border-border/60 shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className={`p-6 flex items-start justify-between ${meta.bg} border-b border-border/30`}>
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-2xl ${meta.bg} border ${meta.border} flex items-center justify-center`}>
              <Icon className={`w-5 h-5 ${meta.color}`} />
            </div>
            <div>
              <h3 className="font-display font-extrabold text-lg text-foreground">Add Medicine</h3>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Slot {compartmentNumber} · {meta.label} · {meta.time}
              </p>
            </div>
          </div>
          {!isPending && (
            <button onClick={onClose} className="w-8 h-8 rounded-full bg-muted/40 hover:bg-muted flex items-center justify-center text-muted-foreground">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Content */}
        {success ? (
          <div className="flex flex-col items-center text-center py-10 px-8 gap-4">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-500" />
            </div>
            <div>
              <p className="font-bold text-foreground text-base">Medicine Added</p>
              <p className="text-sm text-muted-foreground mt-1">
                Prescription created and{deviceId ? ' IoT device updated.' : ' schedule saved.'}
              </p>
            </div>
            <Button onClick={onSuccess} className="h-11 px-8 rounded-xl font-bold shadow-md shadow-primary/20">Done</Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-4">

            {/* Medicine name */}
            <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">
              Medicine Name *
              <input
                required
                autoFocus
                value={form.medicine_name}
                onChange={e => set('medicine_name', e.target.value)}
                placeholder="e.g. Metformin, Atorvastatin…"
                className="mt-2 w-full h-12 px-4 rounded-xl border border-border/80 bg-muted/30 outline-none font-semibold text-foreground focus:border-primary/80 text-sm"
              />
            </label>

            {/* Doctor name with autocomplete */}
            <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">
              Prescribed By (Doctor Name)
              <DoctorAutocomplete
                value={form.doctor_name}
                onChange={v => set('doctor_name', v)}
              />
            </label>

            {/* Qty / Days / Total */}
            <div className="grid grid-cols-3 gap-3">
              <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">
                Qty / Dose
                <input
                  type="number" min={1}
                  value={form.quantity_per_dose}
                  onChange={e => set('quantity_per_dose', e.target.value)}
                  className="mt-2 w-full h-12 px-4 rounded-xl border border-border/80 bg-muted/30 outline-none font-semibold text-foreground focus:border-primary/80 text-sm"
                />
              </label>
              <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">
                Total Pills
                <input
                  type="number" min={1}
                  value={form.total_pills}
                  onChange={e => set('total_pills', e.target.value)}
                  className="mt-2 w-full h-12 px-4 rounded-xl border border-border/80 bg-muted/30 outline-none font-semibold text-foreground focus:border-primary/80 text-sm"
                />
              </label>
              <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">
                Days
                <select
                  value={String(form.duration_days)}
                  onChange={e => set('duration_days', e.target.value === 'null' ? null : Number(e.target.value))}
                  className="mt-2 w-full h-12 px-3 rounded-xl border border-border/80 bg-muted/30 outline-none font-semibold text-foreground focus:border-primary/80 text-sm"
                >
                  {DURATION_OPTIONS.map(opt => (
                    <option key={String(opt.value)} value={String(opt.value)}>{opt.label}</option>
                  ))}
                </select>
              </label>
            </div>

            {/* Instructions */}
            <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">
              Instructions (optional)
              <textarea
                value={form.instructions}
                onChange={e => set('instructions', e.target.value)}
                rows={2}
                placeholder="e.g. Take with a full glass of water"
                className="mt-2 w-full px-4 py-3 rounded-xl border border-border/80 bg-muted/30 outline-none font-medium text-foreground text-sm focus:border-primary/80 resize-none"
              />
            </label>

            {/* Schedule preview */}
            <div className={`flex items-center gap-3 p-3 rounded-xl ${meta.bg} border ${meta.border}`}>
              <Icon className={`w-4 h-4 ${meta.color} shrink-0`} />
              <div className="text-xs">
                <span className="font-bold text-foreground">{meta.time}</span>
                <span className="text-muted-foreground font-medium"> · {meta.with_food ? 'After food' : 'Before food'} · Daily</span>
                {form.duration_days && <span className="text-muted-foreground font-medium"> · {form.duration_days} days</span>}
                {!form.duration_days && <span className="text-muted-foreground font-medium"> · Indefinite</span>}
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-destructive/10 rounded-xl text-destructive text-xs font-medium">
                <AlertCircle className="w-4 h-4 shrink-0" /> {error}
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <Button variant="outline" type="button" className="flex-1 h-11 rounded-xl font-bold uppercase tracking-widest text-xs" onClick={onClose} disabled={isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={isPending} className="flex-1 h-11 rounded-xl font-bold uppercase tracking-widest text-xs shadow-lg shadow-primary/20">
                {isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                Add Medicine
              </Button>
            </div>
          </form>
        )}
      </motion.div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MedicineManager() {
  const navigate = useNavigate();
  const { data: patients = [], isLoading: loadingPatients } = useCaregiverPatients();

  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const activePatientId = selectedPatientId ?? patients[0]?.id ?? null;

  const { data: prescriptions = [], isLoading: loadingRx }       = useCaregiverPatientPrescriptions(activePatientId);
  const { data: devices = [],        isLoading: loadingDevices }  = useCaregiverPatientDevices(activePatientId);

  const [addingToSlot, setAddingToSlot] = useState(null); // compartment number 1-4
  const [editingSlot, setEditingSlot] = useState(null); // { compartmentNumber, initialTimes }

  const activeDevice = devices[0] ?? null;
  const { data: dispenserCompartments = [], isLoading: loadingDispenserCompartments } = useDispenserCompartments(activeDevice?.id);

  // Build a 4-slot grid: map existing compartment data + all prescriptions per slot
  const compartmentSlots = useMemo(() => {
    const deviceCompartments = dispenserCompartments?.length ? dispenserCompartments : (activeDevice?.compartments ?? []);
    const byNum = Object.fromEntries(deviceCompartments.map(c => [c.compartment_number, c]));

    return [1, 2, 3, 4].map(n => {
      const deviceSlot = byNum[n] ?? { compartment_number: n, medication_name: null, scheduled_times: [], sub_compartments: [] };
      const meta = SLOT_META[n];
      // Collect ALL active prescriptions that match this slot's time OR compartment_number OR rescheduled times
      const slotRx = prescriptions.filter(rx =>
        (rx.is_active !== false) && (
          rx.compartment_number === n ||
          rx.schedules?.some(s => s.times_of_day?.some(t => t.time === meta.time)) ||
          (deviceSlot.scheduled_times && deviceSlot.scheduled_times.some(st => rx.schedules?.some(s => s.times_of_day?.some(t => t.time === st))))
        )
      );
      return { ...deviceSlot, prescriptions: slotRx, sub_compartments: deviceSlot.sub_compartments ?? [] };
    });
  }, [activeDevice, dispenserCompartments, prescriptions]);

  const reschedule = useRescheduleCompartment();

  function openEditSlot(slot) {
    // Prefer device mapping times (canonical IoT source), fallback to prescriptions
    let times = [];
    const sourceCompartments = dispenserCompartments?.length ? dispenserCompartments : (activeDevice?.compartments ?? []);
    if (sourceCompartments) {
      const devSlot = sourceCompartments.find(c => Number(c.compartment_number) === Number(slot.compartment_number));
      if (devSlot?.scheduled_times && Array.isArray(devSlot.scheduled_times) && devSlot.scheduled_times.length) {
        times = devSlot.scheduled_times;
      }
    }

    if (!times.length) {
      const pres = slot.prescriptions || [];
      if (pres.length > 0) {
        const first = pres[0];
        times = (first.schedules?.[0]?.times_of_day || []).map(t => t.time);
      }
    }

    setEditingSlot({ compartmentNumber: slot.compartment_number, initialTimes: (times || []).join(', ') });
  }

  return (
    <div className="flex flex-col gap-8 py-4">

      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <button onClick={() => navigate('/caregiver/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-2">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em]">Dashboard</span>
          </button>
          <h2 className="text-3xl font-display font-extrabold text-foreground tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Pill className="w-5 h-5 text-primary" />
            </div>
            Medicine Manager
          </h2>
          <p className="text-muted-foreground font-medium text-sm mt-1">
            Add medicines per slot — schedules sync to patient app and IoT device automatically.
          </p>
        </div>
      </div>

      {/* Patient selector */}
      {loadingPatients ? (
        <div className="flex gap-3">
          {[1, 2, 3].map(i => <div key={i} className="h-12 w-28 rounded-2xl bg-muted animate-pulse" />)}
        </div>
      ) : patients.length === 0 ? (
        <div className="p-6 rounded-2xl border border-dashed border-border/60 text-center text-sm text-muted-foreground">
          No linked patients yet. Ask a patient to send you a caregiver invite.
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-1">
          {patients.map(p => (
            <PatientTab
              key={p.id}
              patient={p}
              isActive={p.id === activePatientId}
              onClick={() => setSelectedPatientId(p.id)}
            />
          ))}
        </div>
      )}

      {activePatientId && (
        <>
          {/* Device status strip */}
          {!loadingDevices && (
            <div className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-xs font-medium ${
              activeDevice
                ? 'bg-primary/5 border-primary/20 text-primary'
                : 'bg-muted/20 border-dashed border-border/60 text-muted-foreground'
            }`}>
              <Cpu className="w-4 h-4 shrink-0" />
              {activeDevice
                ? <span>Device <span className="font-bold">{activeDevice.device_name}</span> linked — medicines will sync to IoT compartments automatically.</span>
                : <span>No IoT device linked to this patient. Medicines will be scheduled via app reminders only.</span>
              }
              {activeDevice && (
                <Badge variant={activeDevice.is_active ? 'success' : 'secondary'} className="ml-auto text-[9px] font-black uppercase tracking-wider px-2 h-5 rounded-full">
                  {activeDevice.is_active ? 'online' : 'offline'}
                </Badge>
              )}
            </div>
          )}

          {/* 4 compartment slots */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <User className="w-3.5 h-3.5 text-muted-foreground" />
              <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                {patients.find(p => p.id === activePatientId)?.name ?? ''} — Dispenser Slots
              </p>
            </div>

            {(loadingDevices || loadingRx || loadingDispenserCompartments) ? (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-52 rounded-[2rem] bg-muted animate-pulse" />)}
              </div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {compartmentSlots.map(slot => (
                  <CompartmentSlot
                    key={slot.compartment_number}
                    slot={slot}
                    prescriptions={slot.prescriptions}
                    onAddClick={setAddingToSlot}
                    onEditClick={openEditSlot}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Active prescriptions list */}
          <Card className="rounded-[2rem]">
            <CardHeader className="p-7 border-b border-border/40 flex flex-row items-center justify-between">
              <div>
                <h3 className="font-display font-bold text-lg">Active Medicines</h3>
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-widest mt-0.5">
                  All scheduled medicines for this patient
                </p>
              </div>
              <Badge variant="secondary" className="text-[10px] font-black uppercase tracking-wider px-3 h-6 rounded-full">
                {prescriptions.filter(rx => rx.is_active).length} active
              </Badge>
            </CardHeader>
            <CardContent className="p-7">
              {loadingRx ? (
                <div className="space-y-3">
                  {[1, 2].map(i => <div key={i} className="h-16 rounded-2xl bg-muted animate-pulse" />)}
                </div>
              ) : prescriptions.length === 0 ? (
                <div className="text-center py-10 flex flex-col items-center gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-muted/40 flex items-center justify-center">
                    <Pill className="w-7 h-7 text-muted-foreground/40" />
                  </div>
                  <p className="text-sm text-muted-foreground font-medium">No medicines added yet.</p>
                  <p className="text-xs text-muted-foreground/60">Click any empty slot above to add the first medicine.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {prescriptions.map(rx => <PrescriptionRow key={rx.id} rx={rx} patientId={activePatientId} />)}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Add Medicine Modal */}
      <AnimatePresence>
        {addingToSlot && activePatientId && (
          <AddMedicineModal
            key={addingToSlot}
            patientId={activePatientId}
            deviceId={activeDevice?.id ?? null}
            compartmentNumber={addingToSlot}
            onClose={() => setAddingToSlot(null)}
            onSuccess={() => setAddingToSlot(null)}
          />
        )}
        {editingSlot && activePatientId && (
          <EditScheduleModal
            key={`edit-slot-${editingSlot.compartmentNumber}`}
            patientId={activePatientId}
            deviceId={activeDevice?.id ?? null}
            compartmentNumber={editingSlot.compartmentNumber}
            initialTimes={editingSlot.initialTimes}
            onClose={() => setEditingSlot(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function EditScheduleModal({ patientId, deviceId, compartmentNumber, initialTimes = '', onClose }) {
  const [value, setValue] = useState(initialTimes);
  const [error, setError] = useState('');
  const reschedule = useRescheduleCompartment();
  const [isPending, setPending] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const times = value.split(',').map(t => t.trim()).filter(Boolean);
    if (!times.length) return setError('Enter at least one time in HH:MM format.');

    // Validate each time is HH:MM with minutes 00-59 and hours 00-23
    const timeRe = /^([01]\d|2[0-3]):([0-5]\d)$/;
    const invalid = times.filter(t => !timeRe.test(t));
    if (invalid.length) return setError(`Invalid time: ${invalid[0]}. Use HH:MM (00:00–23:59).`);
    setPending(true);
    try {
      await reschedule.mutateAsync({ patientId, deviceId, compartmentNumber, payload: { times } });
      onClose();
    } catch (err) {
      console.error('Reschedule failed', err);
      setError(err?.response?.data?.message || err?.message || 'Failed to save. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/60 backdrop-blur-md" onClick={() => !isPending && onClose()} />
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="relative z-10 w-full max-w-md bg-card rounded-[2rem] border border-border/60 shadow-2xl overflow-hidden">
        <div className="p-6 border-b border-border/30 flex items-center justify-between">
          <div>
            <h3 className="font-display font-extrabold text-lg text-foreground">Edit Slot {compartmentNumber} Times</h3>
            <p className="text-[10px] text-muted-foreground">Enter times as comma separated HH:MM values (e.g. 08:00, 20:00)</p>
          </div>
          {!isPending && (
            <button onClick={onClose} className="w-8 h-8 rounded-full bg-muted/40 hover:bg-muted flex items-center justify-center text-muted-foreground">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground">Scheduled Times
            <input value={value} onChange={e => { setValue(e.target.value); setError(''); }} placeholder="08:00, 20:00" className="mt-2 w-full h-12 px-4 rounded-xl border border-border/80 bg-muted/30 outline-none font-semibold text-foreground focus:border-primary/80 text-sm" />
          </label>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 rounded-xl text-destructive text-xs font-medium">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}
          <div className="flex gap-3">
            <Button variant="outline" type="button" className="flex-1 h-11 rounded-xl font-bold uppercase tracking-widest text-xs" onClick={onClose} disabled={isPending}>Cancel</Button>
            <Button type="submit" className="flex-1 h-11 rounded-xl font-bold uppercase tracking-widest text-xs" disabled={isPending}>
              {isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save
            </Button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
