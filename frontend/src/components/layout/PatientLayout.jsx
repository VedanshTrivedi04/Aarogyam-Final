import { useState, useRef, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Pill,
  Bell,
  BarChart3,
  UserCircle,
  Settings,
  Menu,
  X,
  LogOut,
  ChevronRight,
  Stethoscope,
  ArrowLeft,
  ShieldAlert,
  LayoutGrid,
  Cpu,
  Trophy,
  Users,
  MapPin,
  ShieldCheck,
  CreditCard,
  Lock,
  Activity,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth.store';
import logoMedicine from '@/assets/logo medicine.png';
import { ChatToastProvider } from '@/components/ui/ChatToast';

const NavLink = ({ to, icon: Icon, label, active, onClick }) => (
  <Link 
    to={to} 
    onClick={onClick}
    className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-semibold text-sm
      ${active 
        ? 'bg-primary text-primary-foreground shadow-elevation-2' 
        : 'text-muted-foreground hover:bg-secondary hover:text-primary'}`}
  >
    <Icon className="w-5 h-5" />
    <span>{label}</span>
    {active && <motion.div layoutId="nav-pill" className="ml-auto"><ChevronRight className="w-4 h-4" /></motion.div>}
  </Link>
);

export const PatientLayout = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, clearSession } = useAuthStore();

  const isCaregiver = user?.role === 'CAREGIVER';
  const isDoctor = user?.role === 'DOCTOR';

  useEffect(() => {
    const handler = (e) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target)) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const settingsItems = isCaregiver
    ? [
        { icon: Settings,   label: 'Clinical Settings', tab: null, base: '/caregiver/settings' },
        { icon: CreditCard, label: 'Subscription Plan',  tab: null, base: '/caregiver/settings' },
      ]
    : isDoctor
    ? [
        { icon: ShieldCheck, label: 'Account Security',  tab: 'security',  base: '/doctor/settings' },
        { icon: Lock,        label: 'Data Privacy',       tab: 'privacy',   base: '/doctor/settings' },
        { icon: Pill,        label: 'Medicine Archives',  tab: 'archives',  base: '/doctor/settings' },
      ]
    : [
        { icon: ShieldCheck, label: 'Account Security',  tab: 'security',     base: '/patient/settings' },
        { icon: CreditCard,  label: 'Subscription Plan', tab: 'subscription', base: '/patient/settings' },
        { icon: Lock,        label: 'Data Privacy',       tab: 'privacy',      base: '/patient/settings' },
        { icon: Pill,        label: 'Medicine Archives',  tab: 'archives',     base: '/patient/settings' },
      ];

  let navItems = [
    { to: '/patient/home',     icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/patient/medicines', icon: Pill,            label: 'My Medicines' },
    { to: '/patient/vitals',   icon: Activity,         label: 'Vitals' },
    { to: '/patient/rewards',   icon: Trophy,       label: 'Rewards' },
    { to: '/patient/family',    icon: Users,        label: 'Family' },
    { to: '/patient/reports',   icon: BarChart3,    label: 'Adherence Reports' },
    { to: '/notifications',    icon: Bell,            label: 'Alerts' },
    { to: '/consult-doctors',  icon: Stethoscope,     label: 'Doctor Connect' },
    { to: '/patient/profile',  icon: UserCircle,      label: 'My Profile' },
    { to: '/patient/settings', icon: Settings,        label: 'Settings' },
  ];

  if (isCaregiver) {
    navItems = [
      { to: '/caregiver/home',         icon: LayoutDashboard, label: 'Family Dashboard' },
      { to: '/caregiver/medicines',     icon: Pill,            label: 'Medicine Manager' },
      { to: '/caregiver/alerts',        icon: Bell,            label: 'Prioritized Alerts' },
      { to: '/caregiver/geofencing',    icon: MapPin,          label: 'Geofencing' },
      { to: '/caregiver/devices',       icon: Cpu,             label: 'IoT Device Manager' },
      { to: '/caregiver/compartments',  icon: LayoutGrid,      label: 'Compartment Logic' },
      { to: '/caregiver/profile',       icon: UserCircle,      label: 'My Profile' },
      { to: '/caregiver/settings',      icon: Settings,        label: 'Clinical Settings' },
    ];
  } else if (isDoctor) {
    navItems = [
      { to: '/doctor/home',     icon: LayoutDashboard, label: 'Registry Overview' },
      { to: '/doctor/critical', icon: ShieldAlert,     label: 'High Risk Flags' },
      { to: '/notifications',   icon: Bell,            label: 'Patient Alerts' },
      { to: '/doctor/profile',  icon: UserCircle,      label: 'My Profile' },
      { to: '/doctor/settings', icon: Settings,        label: 'Clinical Profile' },
    ];
  }

  return (
    <div className="min-h-screen bg-background flex flex-col md:flex-row font-sans">
      <ChatToastProvider />
      {/* Sidebar - Desktop */}
      <aside className="hidden md:flex w-72 flex-col bg-card border-r border-border/50 sticky top-0 h-screen p-6">
        <Link to="/" className="flex items-center gap-3 mb-10 px-2 hover:opacity-80 transition-opacity">
          <img src={logoMedicine} alt="Aarogyam Logo" className="w-10 h-10 object-contain drop-shadow-sm" />
          <span className="font-display font-bold text-2xl text-primary tracking-tight">Aarogyam</span>
        </Link>

        <nav className="flex-1 flex flex-col gap-2">
          {navItems.map((item) => (
            <NavLink 
              key={item.to} 
              {...item} 
              active={location.pathname === item.to} 
            />
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-border/50">
          <Link
            to={isCaregiver ? '/caregiver/profile' : isDoctor ? '/doctor/profile' : '/patient/profile'}
            className="flex items-center gap-4 px-2 mb-6 group hover:opacity-80 transition-opacity"
          >
            <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary font-bold text-lg group-hover:bg-primary group-hover:text-white transition-colors">
              {user?.firstName?.[0]}{user?.lastName?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="font-bold text-sm truncate">{user?.firstName} {user?.lastName}</h4>
              <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground truncate group-hover:text-primary transition-colors">View Profile</p>
            </div>
          </Link>
          <Link 
            to="/"
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-muted-foreground hover:bg-secondary hover:text-primary transition-all font-semibold text-sm mb-2"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Home</span>
          </Link>
          <button 
            onClick={clearSession}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-destructive hover:bg-destructive/10 transition-all font-semibold text-sm"
          >
            <LogOut className="w-5 h-5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Mobile Nav Header */}
      <header className="md:hidden flex items-center justify-between p-4 bg-card border-b border-border sticky top-0 z-40">
        <Link to="/" className="flex items-center gap-2">
          <img src={logoMedicine} alt="Aarogyam Logo" className="w-8 h-8 object-contain" />
          <span className="font-display font-bold text-xl text-primary tracking-tight">Aarogyam</span>
        </Link>
        <button onClick={() => setIsMobileMenuOpen(true)} className="p-2 text-foreground">
          <Menu className="w-6 h-6" />
        </button>
      </header>

      {/* Mobile Menu Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm md:hidden"
          >
            <motion.aside 
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              className="w-4/5 max-w-sm h-full bg-card p-6 flex flex-col"
            >
              <div className="flex items-center justify-between mb-8">
                <Link to="/" className="flex items-center gap-2">
                  <img src={logoMedicine} alt="Aarogyam Logo" className="w-8 h-8 object-contain" />
                  <span className="font-display font-bold text-xl text-primary">Aarogyam</span>
                </Link>
                <button onClick={() => setIsMobileMenuOpen(false)} className="p-2"><X className="w-6 h-6" /></button>
              </div>
              <nav className="flex flex-col gap-2">
                {navItems.map((item) => (
                  <NavLink 
                    key={item.to} 
                    {...item} 
                    active={location.pathname === item.to} 
                    onClick={() => setIsMobileMenuOpen(false)}
                  />
                ))}
              </nav>
              <button 
                onClick={clearSession}
                className="mt-auto flex items-center gap-3 px-4 py-3 rounded-xl text-destructive hover:bg-destructive/10 transition-all font-semibold text-sm"
              >
                <LogOut className="w-5 h-5" />
                <span>Sign Out</span>
              </button>
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 h-screen overflow-y-auto pb-12">
        <header className="hidden md:flex items-center justify-between px-10 py-6 bg-background/80 backdrop-blur-md sticky top-0 z-30">
          <div>
            <h2 className="text-xl font-display font-bold text-foreground">
              {isCaregiver ? 'Caregiver Portal' : isDoctor ? 'Doctor Portal' : 'Patient Portal'}
            </h2>
            <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
          </div>
          <div className="flex items-center gap-4">
             <div className="flex items-center gap-1.5 bg-success/10 text-success px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border border-success/20">
               <div className="w-1 h-1 rounded-full bg-success animate-pulse" />
               Live Clinical Stream
             </div>
            <Link to="/notifications" className="p-2.5 rounded-full bg-card border border-border hover:bg-secondary transition-all relative">
              <Bell className="w-5 h-5 text-muted-foreground" />
              <span className="absolute top-2.5 right-2.5 w-1.5 h-1.5 bg-accent rounded-full border-2 border-card" />
            </Link>

            {/* Settings dropdown */}
            <div ref={settingsRef} className="relative">
              <button
                onClick={() => setSettingsOpen(o => !o)}
                className={`p-2.5 rounded-full border transition-all ${settingsOpen ? 'bg-primary text-primary-foreground border-primary' : 'bg-card border-border hover:bg-secondary text-muted-foreground'}`}
              >
                <Settings className="w-5 h-5" />
              </button>

              <AnimatePresence>
                {settingsOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 8, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-2 w-56 bg-card border border-border/60 rounded-2xl shadow-xl shadow-black/10 overflow-hidden z-50"
                  >
                    <div className="px-4 py-3 border-b border-border/40 bg-secondary/30">
                      <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Settings</p>
                    </div>
                    {settingsItems.map(({ icon: Icon, label, tab, base }) => (
                      <button
                        key={label}
                        onClick={() => {
                          navigate(tab ? `${base}?tab=${tab}` : base);
                          setSettingsOpen(false);
                        }}
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm font-semibold text-foreground hover:bg-secondary transition-colors text-left"
                      >
                        <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        {label}
                      </button>
                    ))}
                    <div className="border-t border-border/40">
                      <button
                        onClick={() => { clearSession(); setSettingsOpen(false); }}
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm font-semibold text-destructive hover:bg-destructive/10 transition-colors"
                      >
                        <div className="w-7 h-7 rounded-lg bg-destructive/10 flex items-center justify-center shrink-0">
                          <LogOut className="w-3.5 h-3.5" />
                        </div>
                        Sign Out
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="w-10 h-10 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-bold shadow-inner">
              {user?.firstName?.[0]}{user?.lastName?.[0]}
            </div>
          </div>
        </header>

        <div className="px-6 md:px-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
