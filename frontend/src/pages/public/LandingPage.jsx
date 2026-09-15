import { useState, useEffect, useRef, useMemo } from 'react';
import { motion, useInView } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Shield, Heart, Users, CheckCircle, ArrowRight,
  Star, Activity, Bell, Smartphone,
  Zap, BarChart3, MessageCircle, Sparkles,
  Phone, Mail, MapPin, Globe, ExternalLink, Share2,
  Play, ShieldCheck
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import LogoLoop from '@/components/ui/LogoLoop';
import heroImage from '@/assets/final_hero.png';
import heroWomanBg from '@/assets/hero_woman_bg.png';
import logoMedicine from '@/assets/logo medicine.png';
import { useAuthStore } from '@/stores/auth.store';
import PillNav from '@/components/ui/PillNav';
import {
  SiApple, SiSamsung, SiGoogle,
  SiFitbit, SiPhilipshue
} from 'react-icons/si';
import { FaHospital, FaHeartbeat, FaLaptopMedical, FaMedkit } from 'react-icons/fa';

/* ───── Animated Counter ───── */
const Counter = ({ end, suffix = '', duration = 2000 }) => {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const step = end / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= end) { setCount(end); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 16);
    return () => clearInterval(timer);
  }, [inView, end, duration]);
  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
};

/* ───── Floating Particles ───── */
// eslint-disable-next-line no-unused-vars
const Particles = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none">
    {[...Array(6)].map((_, i) => (
      <motion.div key={i}
        className="absolute rounded-full opacity-20"
        style={{
          width: 8 + i * 6, height: 8 + i * 6,
          background: i % 2 === 0 ? 'var(--primary)' : 'var(--accent)',
          left: `${15 + i * 14}%`, top: `${20 + (i % 3) * 25}%`,
        }}
        animate={{ y: [0, -30, 0], x: [0, 15, 0], scale: [1, 1.2, 1] }}
        transition={{ duration: 4 + i, repeat: Infinity, ease: 'easeInOut', delay: i * 0.5 }}
      />
    ))}
  </div>
);

/* ───── Section Fade-In Wrapper ───── */
const FadeIn = ({ children, className = '', delay = 0 }) => {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });
  return (
    <motion.div ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={className}
    >{children}</motion.div>
  );
};

/* ───── Bento Card ───── */
const BentoCard = ({ icon: Icon, title, description, gradient, className, link, children }) => {
  const card = (
    <motion.div whileHover={{ y: -4, scale: 1.01 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className={`relative group p-8 bg-card/25 backdrop-blur-xl rounded-3xl border border-white/40 dark:border-white/10 shadow-elevation-1 hover:shadow-elevation-3 hover:bg-card/35 transition-all duration-500 overflow-hidden flex flex-col justify-between ${className}`}
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
        style={{ background: gradient }} />
      <div className="relative z-10 max-w-[80%]">
        <div className="w-14 h-14 rounded-2xl bg-secondary/80 backdrop-blur-md flex items-center justify-center text-primary mb-6 group-hover:scale-110 group-hover:rotate-3 transition-transform duration-300 shadow-sm">
          <Icon className="w-7 h-7" />
        </div>
        <h3 className="text-2xl font-display font-bold text-foreground mb-3 tracking-tight">{title}</h3>
        <p className="text-muted-foreground leading-relaxed text-[15px] md:text-[16px]">{description}</p>
      </div>
      {children}
    </motion.div>
  );

  if (link) return <Link to={link} className={className}>{card}</Link>;
  return card;
};

/* ───── Step Card ───── */
const StepCard = ({ number, title, description, icon: Icon, delay, gradient }) => (
  <FadeIn delay={delay} className="relative h-full">
    <motion.div whileHover={{ y: -8 }}
      className="relative group h-full p-8 bg-card/25 backdrop-blur-xl rounded-3xl border border-white/40 dark:border-white/10 shadow-elevation-1 hover:shadow-elevation-3 hover:bg-card/35 transition-all duration-500 overflow-hidden flex flex-col items-center text-center z-10"
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700" style={{ background: gradient }} />
      {/* Huge Watermark Number */}
      <div className="absolute -right-4 -top-8 text-[180px] font-display font-extrabold text-foreground/[0.04] select-none pointer-events-none group-hover:text-primary/[0.08] transition-colors duration-500 leading-none">
        {number}
      </div>
      
      <div className="relative z-10 mb-8 mt-4">
        <div className="w-20 h-20 rounded-2xl bg-secondary/80 backdrop-blur-md flex items-center justify-center text-primary group-hover:scale-110 group-hover:rotate-6 transition-transform duration-500 shadow-sm relative">
          <Icon className="w-10 h-10 relative z-10" />
          <div className="absolute inset-0 bg-primary/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        </div>
      </div>
      
      <div className="relative z-10">
        <h3 className="text-2xl font-display font-bold text-foreground mb-4 tracking-tight">{title}</h3>
        <p className="text-muted-foreground text-[16px] leading-relaxed">{description}</p>
      </div>
    </motion.div>
  </FadeIn>
);

/* ───── Pricing Card ───── */
const PricingCard = ({ plan, price, period, features, highlighted, delay }) => (
  <FadeIn delay={delay} className="h-full">
    <motion.div
      whileHover={{ y: -8 }}
      className={`relative h-full p-8 rounded-3xl border-2 flex flex-col gap-8 transition-all duration-500 overflow-hidden backdrop-blur-xl ${
        highlighted
          ? 'bg-primary/20 border-primary shadow-[0_20px_50px_rgba(11,110,122,0.2)]'
          : 'bg-card/25 border-white/40 dark:border-white/10 shadow-elevation-1 hover:bg-card/35'
      }`}
    >
      {highlighted && (
        <div className="absolute top-0 right-0">
          <div className="bg-accent text-white text-[10px] font-bold px-4 py-1.5 uppercase tracking-wider rounded-bl-xl shadow-lg">
            Most Popular
          </div>
        </div>
      )}

      <div className="relative z-10">
        <h3 className={`text-xl font-display font-bold mb-4 ${highlighted ? 'text-primary' : 'text-foreground'}`}>{plan}</h3>
        <div className="flex items-baseline gap-1 mb-6">
          <span className="text-5xl font-display font-extrabold text-foreground">{price}</span>
          {period && <span className="text-muted-foreground font-medium text-lg">/{period}</span>}
        </div>
        
        <ul className="flex flex-col gap-4">
          {features.map((f, i) => (
            <li key={i} className="flex items-start gap-3">
              <div className={`mt-1 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${highlighted ? 'bg-primary/20 text-primary' : 'bg-muted/80 text-muted-foreground'}`}>
                <CheckCircle className="w-3.5 h-3.5" />
              </div>
              <span className="text-muted-foreground text-[15px] leading-snug">{f}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto relative z-10">
        <Button 
          variant={highlighted ? 'default' : 'outline'} 
          className={`w-full h-12 rounded-2xl font-bold transition-all duration-300 ${highlighted ? 'shadow-lg shadow-primary/20 hover:scale-[1.02]' : 'bg-white/30 hover:bg-white/50 border-white/40'}`}
        >
          {plan === 'Basic' ? 'Get Started' : 'Upgrade Now'}
        </Button>
      </div>
    </motion.div>
  </FadeIn>
);

/* ───── Testimonial Card ───── */
const TestimonialCard = ({ quote, author, role, rating = 5 }) => (
  <div className="p-7 bg-card/25 backdrop-blur-xl rounded-2xl border border-white/40 dark:border-white/10 shadow-elevation-1 flex flex-col gap-5 hover:bg-card/35 hover:shadow-elevation-2 transition-all">
    <div className="flex gap-1">
      {[...Array(rating)].map((_, i) => <Star key={i} className="w-4 h-4 fill-accent text-accent" />)}
    </div>
    <p className="text-foreground/80 italic leading-relaxed">"{quote}"</p>
    <div className="flex items-center gap-3 mt-auto">
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/30 to-accent/30 flex items-center justify-center text-primary font-bold text-sm">
        {author.charAt(0)}
      </div>
      <div>
        <h4 className="font-bold text-sm text-foreground">{author}</h4>
        <p className="text-xs text-muted-foreground">{role}</p>
      </div>
    </div>
  </div>
);

/* ═══════════════════════ MAIN PAGE ═══════════════════════ */
export default function LandingPage() {
  // const [mobileMenu, setMobileMenu] = useState(false);
  // const [scrolled, setScrolled] = useState(false);
  const user = useAuthStore(state => state.user);
  const isAuthenticated = useAuthStore(state => !!state.accessToken);

  const dashboardPath = useMemo(() => {
    if (user?.role === 'DOCTOR') return '/doctor';
    if (user?.role === 'CAREGIVER') return '/caregiver';
    return '/dashboard';
  }, [user?.role]);

  const partnerLogos = useMemo(() => [
    { node: <FaHospital />, title: 'AIIMS Network' },
    { node: <SiGoogle />, title: 'Google Health' },
    { node: <SiApple />, title: 'Apple Health' },
    { node: <FaHeartbeat />, title: 'Medanta' },
    { node: <SiSamsung />, title: 'Samsung Health' },
    { node: <FaLaptopMedical />, title: 'Practo' },
    { node: <SiFitbit />, title: 'Fitbit' },
    { node: <FaMedkit />, title: 'PharmEasy' },
    { node: <SiPhilipshue />, title: 'Philips Healthcare' },
  ], []);

  const navItems = useMemo(() => [
    { label: 'Features', href: '#features' },
    { label: 'How It Works', href: '#how-it-works' },
    { label: 'Pricing', href: '#pricing' },
    { label: 'Testimonials', href: '#testimonials' },
    { label: 'Smart Dispenser', href: '/smart-dispenser', pushRight: true },
    isAuthenticated ? { label: 'Dashboard', href: dashboardPath, isHighlighted: true } : { label: 'Login', href: '/login' },
    !isAuthenticated ? { label: 'Sign Up', href: '/register', isHighlighted: true } : null
  ].filter(Boolean), [isAuthenticated, dashboardPath]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="min-h-screen selection:bg-primary/20 overflow-x-hidden relative isolate">

      {/* ────── HOME PAGE BACKGROUND IMAGE (RELATIVE TO PAGE SCROLL) ────── */}
      <div 
        className="absolute inset-0 bg-cover bg-center bg-no-repeat z-0 pointer-events-none transition-opacity duration-700"
        style={{ backgroundImage: `url(${heroWomanBg})` }}
      />
      {/* Light minimal overlay for crystal clear background image visibility */}
      <div className="absolute inset-0 bg-background/10 backdrop-blur-[0px] z-[1] pointer-events-none" />

      {/* ────── NAVBAR ────── */}
      <PillNav
        logo={logoMedicine}
        logoAlt="Aarogyam Logo"
        items={navItems}
        className="fixed top-4 left-1/2 -translate-x-1/2 z-50"
        ease="power2.easeOut"
        baseColor="rgba(255, 255, 255, 0.45)"
        pillColor="#0B6E7A"
        hoveredPillTextColor="#0B6E7A"
        pillTextColor="#ffffff"
        initialLoadAnimation={false}
      />

      {/* ────── HERO ────── */}
      <section className="relative pt-32 pb-24 px-6 overflow-hidden bg-transparent">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
          {/* Left Column: Text Content */}
          <div className="flex flex-col items-start text-left gap-8 relative z-10">
            <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
              className="px-4 py-1.5 rounded-full bg-primary/5 text-primary font-bold text-xs flex items-center gap-2 border border-primary/10"
            >
              <Users className="w-4 h-4" />
              Trusted by 10,000+ Patients Across India
            </motion.div>

            <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.8 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-display font-extrabold tracking-tight leading-[1.1] text-foreground"
            >
              Your Health, <br />
              <span className="relative inline-block mt-2">
                <span className="text-primary">Never Missed.</span>
                <motion.svg className="absolute -bottom-4 left-0 w-full" viewBox="0 0 300 20" fill="none" preserveAspectRatio="none">
                   <motion.path d="M5 15Q150 5 295 15" stroke="currentColor" strokeWidth="4" strokeLinecap="round" className="text-primary/30" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 1, duration: 0.8 }} />
                </motion.svg>
              </span>
            </motion.h1>

            <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
              className="text-lg md:text-xl text-muted-foreground max-w-xl leading-relaxed"
            >
              A clinical-grade health companion that tracks your medication schedules,
              sends smart reminders, and keeps your care team connected — all in one beautiful app.
            </motion.p>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
              className="flex flex-col sm:flex-row gap-4 w-full"
            >
              <Link to="/register" className="flex-1 sm:flex-none">
                <Button className="h-16 px-10 text-lg shadow-xl shadow-primary/20 rounded-2xl bg-primary hover:bg-primary/90 flex items-center gap-3 w-full">
                  Start Free Trial <ArrowRight className="w-6 h-6" />
                </Button>
              </Link>
              <Link to="/demo" className="flex-1 sm:flex-none">
                <Button variant="outline" className="h-16 px-10 text-lg rounded-2xl border-2 flex items-center gap-3 w-full">
                  <Play className="w-5 h-5 fill-foreground" /> Watch Demo
                </Button>
              </Link>
            </motion.div>

            {/* Feature Icons Row */}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
              className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-8 mt-4 border-t border-border/50 w-full"
            >
              <div className="flex flex-col gap-2">
                <ShieldCheck className="w-6 h-6 text-primary" />
                <span className="text-xs font-bold text-foreground">HIPAA Compliant</span>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">Your data is 100% secure</span>
              </div>
              <div className="flex flex-col gap-2">
                <Bell className="w-6 h-6 text-primary" />
                <span className="text-xs font-bold text-foreground">Smart Reminders</span>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">Never miss a dose</span>
              </div>
              <div className="flex flex-col gap-2">
                <Users className="w-6 h-6 text-primary" />
                <span className="text-xs font-bold text-foreground">Caregiver Alerts</span>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">Stay informed, always</span>
              </div>
              <div className="flex flex-col gap-2">
                <BarChart3 className="w-6 h-6 text-primary" />
                <span className="text-xs font-bold text-foreground">Adherence Insights</span>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">Track. Improve. Stay healthy.</span>
              </div>
            </motion.div>
          </div>

          {/* Right Column: Hero Image/Mockup */}
          <motion.div 
            initial={{ opacity: 0, x: 40 }} 
            animate={{ 
              opacity: 1, 
              x: 0,
              y: [0, -20, 0]
            }} 
            transition={{ 
              opacity: { delay: 0.3, duration: 1 },
              x: { delay: 0.3, duration: 1 },
              y: { duration: 5, repeat: Infinity, ease: "easeInOut" }
            }}
            className="relative flex justify-center items-center"
          >
            <img 
              src={heroImage} 
              alt="Aarogyam App and Dispenser" 
              className="relative z-10 w-full h-auto"
              style={{ filter: 'drop-shadow(0 20px 30px rgba(11,110,122,0.15)) drop-shadow(0 10px 10px rgba(0,0,0,0.1))' }}
            />
          </motion.div>
        </div>
      </section>

      {/* ────── TRUSTED BY / LOGO LOOP ────── */}
      <section className="relative py-10 bg-white/10 dark:bg-slate-900/10 backdrop-blur-md border-y border-white/20">
        <div className="max-w-7xl mx-auto px-6">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center text-sm font-semibold text-muted-foreground uppercase tracking-widest mb-8"
          >
            Trusted by Leading Healthcare Organizations
          </motion.p>
          <div className="relative h-[50px] overflow-hidden">
            <LogoLoop
              logos={partnerLogos}
              speed={60}
              direction="left"
              logoHeight={36}
              gap={80}
              hoverSpeed={0}
              scaleOnHover
              fadeOut
              fadeOutColor="transparent"
              ariaLabel="Trusted healthcare partners"
              className="text-muted-foreground/50 hover:text-muted-foreground/70 transition-colors"
            />
          </div>
        </div>
      </section>

      {/* ────── STATS BANNER ────── */}
      <section id="stats" className="relative">
        <div className="bg-primary/40 backdrop-blur-xl border-y border-white/20 py-14 shadow-lg">
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
            {[
              { value: 10000, suffix: '+', label: 'Active Patients' },
              { value: 98, suffix: '%', label: 'Adherence Rate' },
              { value: 500, suffix: '+', label: 'Partner Doctors' },
              { value: 15, suffix: 'L+', label: 'Doses Tracked' },
            ].map((s, i) => (
              <FadeIn key={i} delay={i * 0.1} className="text-center">
                <h3 className="text-3xl md:text-4xl font-display font-extrabold text-white">
                  <Counter end={s.value} suffix={s.suffix} />
                </h3>
                <p className="text-white/80 text-sm font-semibold uppercase tracking-wider mt-2">{s.label}</p>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ────── FEATURES (BENTO BOX) ────── */}
      <section id="features" className="py-32 px-6 relative overflow-hidden bg-transparent">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] max-w-[800px] max-h-[800px] bg-primary/5 rounded-full blur-[120px] pointer-events-none -z-10" />
        <div className="absolute top-0 right-0 w-[40vw] h-[40vw] bg-accent/5 rounded-full blur-[100px] pointer-events-none -z-10" />
        
        <div className="max-w-7xl mx-auto">
          <FadeIn className="text-center mb-20">
            <span className="inline-block py-1.5 px-4 rounded-full bg-primary/10 text-primary font-bold text-sm uppercase tracking-widest mb-4">Core Features</span>
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-extrabold text-foreground mt-3 tracking-tight">
              Everything You Need to <span className="text-primary bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/70">Stay Healthy</span>
            </h2>
            <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto mt-6">
              Modern technology meets clinical precision — designed for patients and caregivers alike.
            </p>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 auto-rows-[300px]">
            {/* Box 1: Smart Reminders (Large) */}
            <BentoCard
              className="md:col-span-2 row-span-1"
              icon={Bell}
              title="Smart Reminders"
              description="Multi-channel alerts via WhatsApp, SMS, Push, and Voice calls so you never miss a dose."
              gradient="linear-gradient(135deg, rgba(11,110,122,0.08), transparent)"
            >
              <div className="hidden md:flex absolute right-8 top-1/2 -translate-y-1/2 flex-col gap-3 opacity-30 group-hover:opacity-100 transition-opacity duration-500">
                <motion.div className="bg-primary text-white text-xs font-semibold py-2 px-5 rounded-full shadow-lg shadow-primary/20 flex items-center gap-2" initial={{x:20, opacity:0}} whileHover={{x:0, opacity:1}} transition={{delay:0.1}}><MessageCircle className="w-3 h-3"/> WhatsApp: Time for Metformin</motion.div>
                <motion.div className="bg-accent text-white text-xs font-semibold py-2 px-5 rounded-full shadow-lg shadow-accent/20 flex items-center gap-2 -ml-6" initial={{x:20, opacity:0}} whileHover={{x:0, opacity:1}} transition={{delay:0.2}}><Smartphone className="w-3 h-3"/> SMS: Dose at 9:00 AM</motion.div>
              </div>
            </BentoCard>

            {/* Box 2: Consult Doctor (Small) */}
            <BentoCard
              className="col-span-1 row-span-1"
              icon={Shield}
              title="Consult Doctor"
              description="Connect with verified specialists anytime via call or chat."
              gradient="linear-gradient(135deg, rgba(39,174,96,0.08), transparent)"
              link="/consult-doctors"
            >
              <div className="absolute top-10 right-10 flex items-center justify-center">
                <div className="absolute w-4 h-4 bg-green-500 rounded-full animate-ping opacity-75" />
                <div className="relative w-4 h-4 bg-green-500 rounded-full border-2 border-white" />
              </div>
            </BentoCard>

            {/* Box 3: IoT Pillbox (Small) */}
            <BentoCard
              className="col-span-1 row-span-1"
              icon={Zap}
              title="IoT Pillbox"
              description="Connect your smart pillbox for automated tracking."
              gradient="linear-gradient(135deg, rgba(139,92,246,0.08), transparent)"
            >
              <div className="absolute bottom-8 right-8">
                 <motion.div className="w-16 h-16 rounded-full border border-purple-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.2)]" animate={{scale:[1, 1.15, 1], opacity:[0.5, 1, 0.5]}} transition={{duration:2, repeat:Infinity}}>
                   <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center shadow-lg"><Smartphone className="w-4 h-4 text-white"/></div>
                 </motion.div>
              </div>
            </BentoCard>

            {/* Box 4: Adherence Reports (Large) */}
            <BentoCard
              className="md:col-span-2 row-span-1"
              icon={BarChart3}
              title="Adherence Reports"
              description="Beautiful visualizations of your progress, exportable as PDF for hospital visits."
              gradient="linear-gradient(135deg, rgba(245,166,35,0.08), transparent)"
            >
              <div className="absolute bottom-0 right-10 flex items-end gap-3 h-32 opacity-40 group-hover:opacity-100 transition-opacity duration-500 overflow-hidden pt-4 px-4 bg-gradient-to-t from-background/80 to-transparent rounded-t-2xl">
                <motion.div className="w-10 bg-accent/40 rounded-t-lg" initial={{height:'30%'}} whileHover={{height:'60%'}} />
                <motion.div className="w-10 bg-accent/70 rounded-t-lg" initial={{height:'50%'}} whileHover={{height:'85%'}} transition={{delay:0.1}}/>
                <motion.div className="w-10 bg-accent rounded-t-lg" initial={{height:'40%'}} whileHover={{height:'100%'}} transition={{delay:0.2}}/>
              </div>
            </BentoCard>

            {/* Box 5: Caregiver Portal (Large) */}
            <BentoCard
              className="md:col-span-2 row-span-1"
              icon={Users}
              title="Caregiver Portal"
              description="Monitor your loved ones in real-time with priority-sorted alert feeds."
              gradient="linear-gradient(135deg, rgba(239,68,68,0.08), transparent)"
              link="/caregiver"
            >
              <div className="absolute right-12 top-1/2 -translate-y-1/2 flex items-center opacity-40 group-hover:opacity-100 transition-opacity duration-500">
                <motion.div className="w-14 h-14 rounded-full border-4 border-white bg-red-100 shadow-lg z-20 flex items-center justify-center" animate={{y:[0,-5,0]}} transition={{duration:3, repeat:Infinity}}><Users className="w-6 h-6 text-red-500"/></motion.div>
                <div className="w-12 border-t-2 border-dashed border-red-200 -ml-4" />
                <motion.div className="w-14 h-14 rounded-full border-4 border-white bg-red-50 shadow-lg z-10 -ml-4 flex items-center justify-center" animate={{y:[0,5,0]}} transition={{duration:3, repeat:Infinity, delay:1}}><Heart className="w-6 h-6 text-red-400"/></motion.div>
              </div>
            </BentoCard>

            {/* Box 6: AI Risk Score (Small) */}
            <BentoCard
              className="col-span-1 row-span-1"
              icon={Sparkles}
              title="AI Risk Score"
              description="ML-powered prediction of non-adherence risk."
              gradient="linear-gradient(135deg, rgba(59,130,246,0.08), transparent)"
            >
              <div className="absolute right-8 bottom-8 group-hover:rotate-180 group-hover:scale-110 transition-all duration-700 origin-center">
                <Sparkles className="w-20 h-20 text-blue-500/20 drop-shadow-lg" />
              </div>
            </BentoCard>
          </div>
        </div>
      </section>

      {/* ────── HOW IT WORKS ────── */}
      <section id="how-it-works" className="py-32 px-6 relative bg-transparent">
        <div className="max-w-7xl mx-auto">
          <FadeIn className="text-center mb-24">
            <span className="inline-block py-1.5 px-4 rounded-full bg-accent/10 text-accent font-bold text-sm uppercase tracking-widest mb-4">How It Works</span>
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-extrabold text-foreground mt-3 tracking-tight">
              Get Started in <span className="text-primary bg-clip-text text-transparent bg-gradient-to-r from-accent to-accent/70">3 Simple Steps</span>
            </h2>
          </FadeIn>
          
          <div className="relative grid md:grid-cols-3 gap-12 md:gap-8">
            {/* Animated Connection Path (Desktop only) */}
            <div className="hidden md:block absolute top-[110px] left-[15%] right-[15%] h-1 bg-border/50 rounded-full overflow-hidden">
              <motion.div 
                className="h-full bg-gradient-to-r from-transparent via-primary to-transparent w-1/3"
                animate={{ x: ['-100%', '300%'] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              />
            </div>
            
            <StepCard number="1" icon={Smartphone} title="Create Your Profile" description="Sign up in 30 seconds. Add your medications, dosages, and daily schedule." delay={0} gradient="linear-gradient(135deg, rgba(11,110,122,0.06), transparent)" />
            <StepCard number="2" icon={Bell} title="Get Smart Reminders" description="Receive perfectly timed alerts on WhatsApp, SMS, or rich push notifications." delay={0.2} gradient="linear-gradient(135deg, rgba(245,166,35,0.06), transparent)" />
            <StepCard number="3" icon={Activity} title="Track & Improve" description="Monitor your adherence with beautiful reports and get AI-driven health insights." delay={0.4} gradient="linear-gradient(135deg, rgba(39,174,96,0.06), transparent)" />
          </div>
        </div>
      </section>

      {/* ────── PRICING ────── */}
      <section id="pricing" className="py-32 px-6 relative overflow-hidden bg-transparent">
        <div className="absolute -bottom-24 -left-24 w-[400px] h-[400px] bg-accent/5 rounded-full blur-[100px] pointer-events-none" />
        
        <div className="max-w-7xl mx-auto">
          <FadeIn className="text-center mb-20">
            <span className="inline-block py-1.5 px-4 rounded-full bg-primary/10 text-primary font-bold text-sm uppercase tracking-widest mb-4">Pricing Plans</span>
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-extrabold text-foreground mt-3 tracking-tight">
              Simple, Transparent <span className="text-primary bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/70">Choices</span>
            </h2>
            <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto mt-6">Choose the plan that fits your family's needs perfectly.</p>
          </FadeIn>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            <PricingCard delay={0} plan="Basic" price="₹0" period="forever"
              features={['Up to 3 medications', 'Push notifications', 'Basic adherence report', 'Single caregiver link', 'Email support']} />
            <PricingCard delay={0.1} plan="Pro" price="₹99" period="month" highlighted
              features={['Up to 10 medications', 'WhatsApp + SMS reminders', 'AI Risk Score', 'Weekly AI Insights', 'Caregiver alerts', 'PDF report exports', 'Priority support']} />
            <PricingCard delay={0.2} plan="Ultimate" price="₹299" period="month"
              features={['Unlimited medications', 'Voice call reminders', 'Real-time AI Insights', 'IoT smart pillbox', 'Geofence reminders', 'Auto pharmacy refill', '24/7 Concierge']} />
          </div>
        </div>
      </section>

      {/* ────── TESTIMONIALS ────── */}
      <section id="testimonials" className="py-28 px-6 bg-transparent">
        <div className="max-w-7xl mx-auto">
          <FadeIn className="text-center mb-16">
            <span className="text-primary font-bold text-sm uppercase tracking-widest">Testimonials</span>
            <h2 className="text-4xl md:text-5xl font-display font-extrabold text-foreground mt-3">
              Loved by <span className="text-primary">Families</span> Across India
            </h2>
          </FadeIn>
          <div className="grid md:grid-cols-3 gap-7">
            <FadeIn delay={0}><TestimonialCard quote="I used to forget my evening pills every second day. Now I'm at 100% adherence for 6 months straight!" author="Rajesh Kumar" role="Type-2 Diabetes Patient" /></FadeIn>
            <FadeIn delay={0.1}><TestimonialCard quote="The caregiver dashboard gives me peace of mind when I'm at work. I can see exactly when Papa takes his medicines." author="Anjali Gupta" role="Daughter & Caregiver" /></FadeIn>
            <FadeIn delay={0.2}><TestimonialCard quote="As a physician, the adherence reports help me make better clinical decisions. The AI risk scores are surprisingly accurate." author="Dr. Meera Patel" role="Cardiologist, AIIMS Delhi" /></FadeIn>
          </div>
        </div>
      </section>

      {/* ────── CTA BANNER ────── */}
      <section className="py-24 px-6">
        <FadeIn>
          <div className="max-w-4xl mx-auto text-center bg-gradient-to-br from-primary/75 to-primary/50 backdrop-blur-xl border border-white/30 rounded-3xl p-12 md:p-16 relative overflow-hidden shadow-2xl shadow-primary/20">
            <div className="absolute inset-0 opacity-10"
              style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 50%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-display font-extrabold text-white mb-4">
                Ready to Take Control of Your Health?
              </h2>
              <p className="text-white/80 text-lg mb-8 max-w-lg mx-auto">
                Join thousands of patients who never miss a dose. Start your free trial today.
              </p>
              {isAuthenticated ? (
                <Link to={dashboardPath}>
                  <Button variant="accent" className="h-14 px-10 text-lg rounded-2xl bg-white text-primary hover:bg-white/90 font-bold shadow-xl">
                    Go to Dashboard <ArrowRight className="ml-2 w-5 h-5" />
                  </Button>
                </Link>
              ) : (
                <Link to="/register">
                  <Button variant="accent" className="h-14 px-10 text-lg rounded-2xl bg-white text-primary hover:bg-white/90 font-bold shadow-xl">
                    Get Started Free <ArrowRight className="ml-2 w-5 h-5" />
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </FadeIn>
      </section>

      {/* ────── FOOTER ────── */}
      <footer className="border-t border-white/20 bg-card/20 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-10">
            <div className="col-span-2">
              <div className="flex items-center gap-2.5 mb-4">
                <img src={logoMedicine} alt="Aarogyam Logo" className="w-9 h-9 object-contain" />
                <span className="font-display font-bold text-xl text-primary">Aarogyam</span>
              </div>
              <p className="text-muted-foreground text-sm leading-relaxed max-w-xs mb-5">
                India's leading digital medicine adherence platform for chronic care. Helping you live healthier, longer.
              </p>
              <div className="flex gap-3">
                {[Phone, Mail, MapPin].map((Icon, i) => (
                  <div key={i} className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center text-muted-foreground hover:text-primary hover:bg-secondary transition-colors cursor-pointer">
                    <Icon className="w-4 h-4" />
                  </div>
                ))}
              </div>
            </div>
            {[
              { title: 'Product', links: ['Features', 'Pricing', 'IoT Pillbox', 'API Docs'] },
              { title: 'Company', links: ['About Us', 'Careers', 'Contact', 'Blog'] },
              { title: 'Legal', links: ['Privacy Policy', 'Terms of Service', 'HIPAA', 'Refund Policy'] },
            ].map((col, i) => (
              <div key={i}>
                <h4 className="font-bold text-sm uppercase tracking-widest text-foreground mb-4">{col.title}</h4>
                <nav className="flex flex-col gap-2.5">
                  {col.links.map(link => (
                    <a key={link} className="text-sm text-muted-foreground hover:text-primary transition-colors cursor-pointer">{link}</a>
                  ))}
                </nav>
              </div>
            ))}
          </div>
        </div>
        <div className="border-t border-border/50">
          <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-muted-foreground">© 2026 Aarogyam Health Systems India Pvt Ltd. All rights reserved.</p>
            <div className="flex gap-4">
              {[Globe, Share2, ExternalLink].map((Icon, i) => (
                <Icon key={i} className="w-4 h-4 text-muted-foreground hover:text-primary transition-colors cursor-pointer" />
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
