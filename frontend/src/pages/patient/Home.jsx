import React from 'react';
import { Link } from 'react-router-dom';
import { useTodaySchedule, useLogDose, useStreak, useAdherenceRate, useDispenseNow } from '@/hooks/useAdherence';
import { usePrescriptions } from '@/hooks/usePrescriptions';
import { useAuthStore } from '@/stores/auth.store';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2,
  Clock,
  Flame,
  AlertTriangle,
  Plus,
  MessageSquare,
  ChevronRight,
  TrendingUp,
  Pill,
  Sun,
  Moon,
  Utensils,
  ShieldAlert,
  Siren,
  MapPin,
  X,
  PhoneCall,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { GamificationWidget } from '@/components/patient/GamificationWidget';
import { axiosInstance } from '@/lib/axios';

// ─── SOS Modal ───────────────────────────────────────────────────────────────
const SOS_STATES = { IDLE: 'idle', CONFIRMING: 'confirming', LOCATING: 'locating', CALLING: 'calling', SUCCESS: 'success', ERROR: 'error' };

function SOSModal({ open, onClose }) {
  const [phase, setPhase] = React.useState(SOS_STATES.IDLE);
  const [countdown, setCountdown] = React.useState(3);
  const [location, setLocation] = React.useState(null);
  const [errorMsg, setErrorMsg] = React.useState('');
  const timerRef = React.useRef(null);

  // Reset when modal opens
  React.useEffect(() => {
    if (open) { setPhase(SOS_STATES.IDLE); setCountdown(3); setLocation(null); setErrorMsg(''); }
    return () => clearInterval(timerRef.current);
  }, [open]);

  // Countdown → locate → call
  React.useEffect(() => {
    if (phase !== SOS_STATES.CONFIRMING) return;
    if (countdown === 0) { locateAndCall(); return; }
    timerRef.current = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(timerRef.current);
  }, [phase, countdown]);

  const locateAndCall = async () => {
    setPhase(SOS_STATES.LOCATING);
    let coords = null;
    try {
      coords = await new Promise((res, rej) =>
        navigator.geolocation.getCurrentPosition(
          p => res({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
          rej,
          { timeout: 8000 }
        )
      );
      setLocation(coords);
    } catch {
      // location unavailable — still proceed
    }
    setPhase(SOS_STATES.CALLING);
    try {
      await axiosInstance.post('/api/v1/notifications/sos/trigger/', {
        latitude: coords?.lat ?? null,
        longitude: coords?.lng ?? null,
        accuracy: coords?.accuracy ?? null,
        timestamp: new Date().toISOString(),
      });
      setPhase(SOS_STATES.SUCCESS);
    } catch (err) {
      setErrorMsg(err?.response?.data?.detail || 'Could not reach emergency services. Please call 112 directly.');
      setPhase(SOS_STATES.ERROR);
    }
  };

  const cancelCountdown = () => { clearTimeout(timerRef.current); setPhase(SOS_STATES.IDLE); setCountdown(3); };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        onClick={phase === SOS_STATES.IDLE ? onClose : undefined}
      >
        <motion.div
          initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.85, opacity: 0 }}
          transition={{ type: 'spring', damping: 20, stiffness: 300 }}
          className="bg-card border border-destructive/40 rounded-3xl shadow-2xl w-full max-w-sm p-8 flex flex-col items-center gap-6 relative"
          onClick={e => e.stopPropagation()}
        >
          {/* Close (only when idle or error) */}
          {(phase === SOS_STATES.IDLE || phase === SOS_STATES.ERROR) && (
            <button onClick={onClose} className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors">
              <X className="w-5 h-5" />
            </button>
          )}

          {/* IDLE */}
          {phase === SOS_STATES.IDLE && (
            <>
              <div className="w-20 h-20 rounded-full bg-destructive/10 flex items-center justify-center">
                <Siren className="w-10 h-10 text-destructive" />
              </div>
              <div className="text-center flex flex-col gap-1">
                <h2 className="text-2xl font-display font-bold text-foreground">Emergency SOS</h2>
                <p className="text-sm text-muted-foreground">This will dispatch an ambulance to your current location. Are you sure?</p>
              </div>
              <div className="flex flex-col gap-3 w-full">
                <Button
                  variant="danger"
                  className="w-full h-14 text-base font-bold uppercase tracking-widest rounded-2xl"
                  onClick={() => setPhase(SOS_STATES.CONFIRMING)}
                >
                  <PhoneCall className="w-5 h-5" /> Call Ambulance
                </Button>
                <Button variant="ghost" className="w-full h-10 text-sm" onClick={onClose}>Cancel</Button>
              </div>
            </>
          )}

          {/* CONFIRMING — countdown */}
          {phase === SOS_STATES.CONFIRMING && (
            <>
              <div className="relative w-24 h-24">
                <svg className="w-24 h-24 -rotate-90">
                  <circle cx="48" cy="48" r="40" strokeWidth="6" stroke="currentColor" fill="none" className="text-destructive/20" />
                  <motion.circle
                    cx="48" cy="48" r="40" strokeWidth="6" stroke="currentColor" fill="none"
                    strokeLinecap="round" strokeDasharray={2 * Math.PI * 40}
                    initial={{ strokeDashoffset: 0 }}
                    animate={{ strokeDashoffset: 2 * Math.PI * 40 }}
                    transition={{ duration: 3, ease: 'linear' }}
                    className="text-destructive"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-4xl font-display font-bold text-destructive">{countdown}</span>
                </div>
              </div>
              <p className="text-center font-semibold text-foreground">Calling ambulance in <span className="text-destructive">{countdown}s</span>…</p>
              <Button variant="outline" className="w-full h-12 font-bold rounded-2xl border-destructive/40 text-destructive" onClick={cancelCountdown}>
                <X className="w-4 h-4" /> Cancel
              </Button>
            </>
          )}

          {/* LOCATING */}
          {phase === SOS_STATES.LOCATING && (
            <>
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center animate-pulse">
                <MapPin className="w-10 h-10 text-primary" />
              </div>
              <p className="text-center font-semibold text-foreground">Fetching your location…</p>
              <p className="text-xs text-muted-foreground text-center">Please allow location access for faster response.</p>
            </>
          )}

          {/* CALLING */}
          {phase === SOS_STATES.CALLING && (
            <>
              <div className="w-20 h-20 rounded-full bg-destructive/10 flex items-center justify-center">
                <PhoneCall className="w-10 h-10 text-destructive animate-bounce" />
              </div>
              <p className="text-center font-semibold text-foreground">Alerting emergency services…</p>
              <div className="w-8 h-8 border-4 border-destructive border-t-transparent rounded-full animate-spin" />
            </>
          )}

          {/* SUCCESS */}
          {phase === SOS_STATES.SUCCESS && (
            <>
              <div className="w-20 h-20 rounded-full bg-success/10 flex items-center justify-center">
                <CheckCircle2 className="w-10 h-10 text-success" />
              </div>
              <div className="text-center flex flex-col gap-1">
                <h2 className="text-xl font-display font-bold text-foreground">Help is on the way!</h2>
                <p className="text-sm text-muted-foreground">Ambulance has been dispatched. Stay calm and keep your phone nearby.</p>
                {location && (
                  <p className="text-xs text-muted-foreground mt-1 flex items-center justify-center gap-1">
                    <MapPin className="w-3 h-3" /> Location shared ({location.lat.toFixed(4)}, {location.lng.toFixed(4)})
                  </p>
                )}
              </div>
              <Button variant="primary" className="w-full h-12 rounded-2xl font-bold" onClick={onClose}>Close</Button>
            </>
          )}

          {/* ERROR */}
          {phase === SOS_STATES.ERROR && (
            <>
              <div className="w-20 h-20 rounded-full bg-destructive/10 flex items-center justify-center">
                <AlertTriangle className="w-10 h-10 text-destructive" />
              </div>
              <div className="text-center flex flex-col gap-1">
                <h2 className="text-xl font-display font-bold text-foreground">Alert Failed</h2>
                <p className="text-sm text-muted-foreground">{errorMsg}</p>
              </div>
              <div className="flex flex-col gap-3 w-full">
                <a href="tel:112" className="w-full">
                  <Button variant="danger" className="w-full h-12 rounded-2xl font-bold"><PhoneCall className="w-4 h-4" /> Call 112 Now</Button>
                </a>
                <Button variant="ghost" className="w-full h-10 text-sm" onClick={onClose}>Close</Button>
              </div>
            </>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ─── Dose Card ────────────────────────────────────────────────────────────────
const DoseCard = ({ time, name, dosage, status, isWithinWindow, onTake, onDispenseNow }) => (
  <motion.div
    whileHover={{ x: 4 }}
    className={`flex items-center gap-4 p-4 rounded-2xl bg-background border transition-all group
      ${status === 'missed' ? 'border-destructive/40 bg-destructive/5' : 'border-border/50 hover:border-primary/30'}`}
  >
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0
      ${status === 'taken'  ? 'bg-success/10 text-success'
      : status === 'missed' ? 'bg-destructive/10 text-destructive'
      : 'bg-secondary text-primary'}`}>
      <Pill className="w-6 h-6" />
    </div>
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 flex-wrap">
        <h4 className="font-bold text-foreground truncate">{name}</h4>
        {status === 'taken'  && <CheckCircle2 className="w-4 h-4 text-success shrink-0" />}
        {status === 'missed' && <ShieldAlert  className="w-4 h-4 text-destructive shrink-0" />}
      </div>
      <p className="text-sm text-muted-foreground font-medium">{dosage} • {time}</p>
      {status === 'pending' && isWithinWindow === false && (
        <p className="text-[10px] text-accent font-semibold mt-0.5 flex items-center gap-1">
          <Clock className="w-3 h-3" /> Outside scheduled window
        </p>
      )}
    </div>
    {status === 'pending' || status === 'snoozed' ? (
      <div className="flex flex-col gap-2 shrink-0">
        <Button variant="secondary" size="sm" onClick={onTake} className="rounded-lg h-9 px-4 text-xs font-bold uppercase tracking-wider">
          Mark Taken
        </Button>
        <Button variant="outline" size="sm" onClick={onDispenseNow} className="rounded-lg h-9 px-4 text-xs font-bold uppercase tracking-wider border-primary/40 text-primary">
          Take Medicine Now
        </Button>
      </div>
    ) : status === 'missed' ? (
      <Badge variant="danger" className="h-8 gap-1 shrink-0"><ShieldAlert className="w-3 h-3" /> Missed</Badge>
    ) : (
      <Badge variant="success" className="h-8 shrink-0">Completed</Badge>
    )}
  </motion.div>
);

const AdherenceRing = ({ percentage }) => {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center">
      <svg className="w-24 h-24 transform -rotate-90">
        <circle className="text-secondary" strokeWidth="8" stroke="currentColor" fill="transparent" r={radius} cx="48" cy="48" />
        <motion.circle 
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
          className="text-primary" 
          strokeWidth="8" 
          strokeDasharray={circumference} 
          strokeLinecap="round" 
          stroke="currentColor" 
          fill="transparent" 
          r={radius} 
          cx="48" 
          cy="48" 
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-display font-bold text-primary">{percentage}%</span>
      </div>
    </div>
  );
};

export default function PatientDashboard() {
  const { user } = useAuthStore();
  const { data: scheduleData, isLoading: isScheduleLoading } = useTodaySchedule();
  const { data: prescriptions = [] } = usePrescriptions({ isActive: true });
  const logDose = useLogDose();
  const dispenseNow = useDispenseNow();
  const { data: streakData } = useStreak();
  const { data: adherenceData } = useAdherenceRate();
  const [sosOpen, setSosOpen] = React.useState(false);

  // 4 fixed meal slots — matches caregiver compartment times
  const MEAL_SLOTS = [
    { key: 'morning_before', label: 'Morning — Before Food', time: '08:00', Icon: Sun,  bg: 'bg-amber-500/10',  border: 'border-amber-200',  color: 'text-amber-500',  with_food: false },
    { key: 'morning_after',  label: 'Morning — After Food',  time: '09:00', Icon: Sun,  bg: 'bg-orange-500/10', border: 'border-orange-200', color: 'text-orange-500', with_food: true  },
    { key: 'night_before',   label: 'Night — Before Food',   time: '20:00', Icon: Moon, bg: 'bg-violet-500/10', border: 'border-violet-200', color: 'text-violet-500', with_food: false },
    { key: 'night_after',    label: 'Night — After Food',    time: '21:00', Icon: Moon, bg: 'bg-indigo-500/10', border: 'border-indigo-200', color: 'text-indigo-500', with_food: true  },
  ];

  const doses = React.useMemo(() => {
    if (!scheduleData) return [];
    return scheduleData.map(item => {
      const d       = new Date(item.scheduled_at);
      const hour    = d.getHours();
      const withFood = !!item.with_food;

      // 1. Try label from backend (most reliable)
      const slotName = (item.label || '').toLowerCase();
      let slot;

      if (slotName.includes('morning') || slotName.includes('breakfast') || slotName.includes('सुबह')) {
        slot = withFood ? 'morning_after' : 'morning_before';
      } else if (slotName.includes('night') || slotName.includes('evening') || slotName.includes('dinner') || slotName.includes('रात')) {
        slot = withFood ? 'night_after' : 'night_before';
      } else if (slotName.includes('afternoon') || slotName.includes('lunch') || slotName.includes('दोपहर')) {
        // Map afternoon to morning slots for now (only 4 slots supported)
        slot = withFood ? 'morning_after' : 'morning_before';
      } else {
        // 2. Fallback: hour-range heuristic (much more robust than exact time match)
        //    Morning  = 04:00 – 13:59
        //    Night    = 14:00 – 03:59 (next day)
        if (hour >= 4 && hour < 14) {
          slot = withFood ? 'morning_after' : 'morning_before';
        } else {
          slot = withFood ? 'night_after' : 'night_before';
        }
      }

      return {
        id:              item.id,
        time:            d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        name:            item.medication_name,
        dosage:          `${item.dose_value || ''}${item.dose_unit || ''}`.trim() || '1 pill',
        status:          item.status.toLowerCase(),
        slot,
        with_food:       item.with_food,
        isWithinWindow:  item.is_within_window,
      };
    });
  }, [scheduleData]);

  const activePrescriptions = React.useMemo(() => prescriptions.filter((rx) => rx.is_active !== false), [prescriptions]);
  const nextRefill = React.useMemo(() => {
    const ordered = [...activePrescriptions]
      .filter((rx) => typeof rx.remaining_quantity === 'number')
      .sort((a, b) => (a.remaining_quantity ?? Number.POSITIVE_INFINITY) - (b.remaining_quantity ?? Number.POSITIVE_INFINITY));
    return ordered[0] || null;
  }, [activePrescriptions]);

  const primaryDoctorName = React.useMemo(() => {
    const candidates = activePrescriptions.map((rx) => rx.prescribed_by).filter(Boolean);
    return candidates[0] || null;
  }, [activePrescriptions]);

  const handleTake = (id) => {
    logDose.mutate({ reminderId: id, status: 'TAKEN' });
  };

  const handleDispenseNow = (id) => {
    dispenseNow.mutate(id, {
      onSuccess: () => alert('Command sent to dispenser. Please bring your hand near the sensor.'),
      onError: (err) => alert('Failed to send command: ' + (err?.response?.data?.detail || err.message))
    });
  };

  return (
    <div className="flex flex-col gap-8 py-4">
      <SOSModal open={sosOpen} onClose={() => setSosOpen(false)} />

      {/* Top Banner: Greeting + Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 bg-primary text-white overflow-hidden relative">
          <div className="absolute right-0 top-0 w-64 h-64 bg-white/10 rounded-full translate-x-1/2 -translate-y-1/2 blur-3xl" />
          <CardContent className="p-8 relative z-10 flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex flex-col gap-2 text-center md:text-left">
              <h2 className="text-3xl font-display font-bold">Good Morning, {user?.full_name?.split(' ')[0] || 'Guest'}! 🎉</h2>
              <p className="text-primary-foreground/80 font-medium">You have {doses.filter(d => d.status === 'pending').length} doses remaining for today. Keep up the momentum!</p>
              <div className="flex flex-wrap gap-4 mt-4 justify-center md:justify-start">
                <Link to="/dashboard/medicines">
                  <Button variant="accent" className="rounded-full shadow-lg"><Plus className="w-4 h-4 mr-2" /> Add Medicine</Button>
                </Link>
                <Link to="/dashboard/reports">
                  <Button variant="ghost" className="rounded-full text-white hover:bg-white/10"><TrendingUp className="w-4 h-4 mr-2" /> View Growth</Button>
                </Link>
              </div>
            </div>
            <div className="flex items-center gap-6 bg-white/10 backdrop-blur-md p-6 rounded-2xl border border-white/20">
              <div className="text-center">
                <h3 className="text-3xl font-display font-bold">{streakData?.current_streak || 0}</h3>
                <p className="text-[10px] font-bold uppercase tracking-widest opacity-70">Day Streak</p>
              </div>
              <div className="w-px h-10 bg-white/20" />
              <Flame className="w-10 h-10 text-accent fill-accent" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-accent/20 bg-accent/5">
          <CardContent className="p-6 flex flex-col items-center gap-4 text-center">
            <div className="flex items-center justify-between w-full mb-2">
              <h3 className="font-bold text-foreground">Health Adherence</h3>
              <Badge variant="warning">On Track</Badge>
            </div>
            <AdherenceRing percentage={Math.round(adherenceData?.summary?.adherence_pct || 0)} />
            <p className="text-sm text-muted-foreground font-medium px-4">Your adherence score based on recent doses.</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Left: Medication Timeline */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-display font-bold flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" /> Today's Schedule
            </h3>
            <div className="flex gap-2">
              <Badge className="cursor-pointer">All</Badge>
              <Badge variant="primary" className="cursor-pointer">Pending</Badge>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            {MEAL_SLOTS.map(slot => {
              const slotDoses = doses.filter(d => d.slot === slot.key);
              const SlotIcon  = slot.Icon;
              return (
                <div key={slot.key} className={`rounded-2xl border overflow-hidden ${slot.border}`}>
                  {/* Slot header */}
                  <div className={`flex items-center gap-3 px-5 py-3 ${slot.bg}`}>
                    <div className={`w-8 h-8 rounded-xl ${slot.bg} flex items-center justify-center shrink-0`}>
                      <SlotIcon className={`w-4 h-4 ${slot.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-extrabold uppercase tracking-widest ${slot.color}`}>{slot.label}</p>
                      <p className="text-[10px] text-muted-foreground font-medium flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" /> {slot.time}
                        <span className="mx-1">·</span>
                        <Utensils className="w-3 h-3" /> {slot.with_food ? 'After food' : 'Before food'}
                      </p>
                    </div>
                    {slotDoses.length > 0 && (
                      <span className={`text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full ${slot.bg} ${slot.color}`}>
                        {slotDoses.filter(d => d.status === 'pending').length} pending
                      </span>
                    )}
                  </div>

                  {/* Medicines */}
                  <div className="px-4 py-3 flex flex-col gap-2 bg-background">
                    {isScheduleLoading ? (
                      <div className="h-14 rounded-xl bg-muted animate-pulse" />
                    ) : slotDoses.length === 0 ? (
                      <p className="text-xs text-muted-foreground italic py-3 text-center">No medicines for this slot.</p>
                    ) : (
                      slotDoses.map(dose => (
                        <DoseCard
                          key={dose.id}
                          {...dose}
                          isWithinWindow={dose.isWithinWindow}
                          onTake={() => handleTake(dose.id)}
                          onDispenseNow={() => handleDispenseNow(dose.id)}
                        />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Alerts & Actions */}
        <div className="flex flex-col gap-6">
          <h3 className="text-xl font-display font-bold">Health Insights</h3>

          {/* SOS Button */}
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => setSosOpen(true)}
            className="relative w-full rounded-2xl overflow-hidden bg-destructive text-white shadow-lg focus:outline-none focus:ring-4 focus:ring-destructive/40"
          >
            {/* Pulse ring */}
            <span className="absolute inset-0 rounded-2xl animate-ping bg-destructive/40 pointer-events-none" />
            <div className="relative z-10 flex items-center justify-center gap-3 px-6 py-5">
              <Siren className="w-7 h-7 shrink-0" />
              <div className="text-left">
                <p className="text-lg font-display font-black uppercase tracking-widest leading-none">SOS</p>
                <p className="text-[11px] font-semibold opacity-80 leading-tight mt-0.5">Emergency — Call Ambulance</p>
              </div>
            </div>
          </motion.button>

          {/* Gamification Widget */}
          <GamificationWidget />

          <Card className="border-accent bg-accent/10 border-dashed">
            <CardContent className="p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center text-white shrink-0">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="flex flex-col gap-1">
                <h4 className="font-bold text-foreground">Upcoming Refill</h4>
                {nextRefill ? (
                  <p className="text-sm text-muted-foreground leading-snug">
                    {nextRefill.name} is running low. Only {nextRefill.remaining_quantity} doses left.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground leading-snug">No active refill alerts right now.</p>
                )}
                <Link to="/dashboard/medicines">
                  <Button variant="accent" size="sm" className="mt-3 w-fit h-8 text-xs font-bold uppercase tracking-wider rounded-lg">Order Refill</Button>
                </Link>
              </div>
            </CardContent>
          </Card>

          <Link to="/consult-doctors">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer group">
            <CardContent className="p-6 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center text-primary">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-foreground">Consult Doctor</h4>
                  <p className="text-xs text-muted-foreground">
                    {primaryDoctorName ? `${primaryDoctorName} is in your care network` : 'Your care team will appear here after prescriptions are added'}
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
            </CardContent>
          </Card>
          </Link>

          <Card className="bg-card">
            <CardContent className="p-6">
              <h4 className="font-bold text-foreground mb-4">Quick Links</h4>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { name: 'Lab Results',    to: '/patient/reports' },
                  { name: 'Prescriptions',  to: '/patient/medicines' },
                  { name: 'Rewards',        to: '/patient/rewards' },
                ].map(link => (
                  <Link key={link.name} to={link.to}>
                    <Button variant="outline" className="w-full justify-start px-4 h-10 text-xs font-semibold rounded-lg bg-background border-border/50">
                      {link.name}
                    </Button>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
