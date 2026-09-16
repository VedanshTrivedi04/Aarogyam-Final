import { useState, useEffect, useRef, useMemo } from 'react';
import { motion, useInView } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Shield, Heart, Users, CheckCircle, ArrowRight,
  Star, Activity, Bell, Smartphone,
  Zap, BarChart3, MessageCircle, Sparkles,
  Phone, Mail, MapPin, Globe, ExternalLink, Share2,
  Play, ShieldCheck, ChevronDown, HelpCircle
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import LogoLoop from '@/components/ui/LogoLoop';
import heroImage from '@/assets/final_hero.png';
import heroWomanBg from '@/assets/media__1789505883649.png';
import logoMedicine from '@/assets/logo medicine.png';
import { useAuthStore } from '@/stores/auth.store';
import PillNav from '@/components/ui/PillNav';
import TextLoop from '@/components/ui/TextLoop';
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
const BentoCard = ({ icon: Icon, title, description, badge, colorTheme = 'teal', className = '', link, children }) => {
  const themes = {
    teal: {
      border: 'border-teal-500/20 hover:border-teal-500/50',
      iconBg: 'bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20',
      badgeBg: 'bg-teal-500/10 text-teal-700 dark:text-teal-300 border-teal-500/20',
      glow: 'from-teal-500/10 via-teal-500/0 to-transparent',
      hoverGlow: 'group-hover:shadow-[0_20px_40px_rgba(11,110,122,0.12)]',
    },
    emerald: {
      border: 'border-emerald-500/20 hover:border-emerald-500/50',
      iconBg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
      badgeBg: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20',
      glow: 'from-emerald-500/10 via-emerald-500/0 to-transparent',
      hoverGlow: 'group-hover:shadow-[0_20px_40px_rgba(39,174,96,0.12)]',
    },
    purple: {
      border: 'border-purple-500/20 hover:border-purple-500/50',
      iconBg: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      badgeBg: 'bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20',
      glow: 'from-purple-500/10 via-purple-500/0 to-transparent',
      hoverGlow: 'group-hover:shadow-[0_20px_40px_rgba(139,92,246,0.12)]',
    },
    amber: {
      border: 'border-amber-500/20 hover:border-amber-500/50',
      iconBg: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
      badgeBg: 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20',
      glow: 'from-amber-500/10 via-amber-500/0 to-transparent',
      hoverGlow: 'group-hover:shadow-[0_20px_40px_rgba(245,166,35,0.12)]',
    },
    rose: {
      border: 'border-rose-500/20 hover:border-rose-500/50',
      iconBg: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
      badgeBg: 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20',
      glow: 'from-rose-500/10 via-rose-500/0 to-transparent',
      hoverGlow: 'group-hover:shadow-[0_20px_40px_rgba(244,63,94,0.12)]',
    },
    blue: {
      border: 'border-blue-500/20 hover:border-blue-500/50',
      iconBg: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
      badgeBg: 'bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20',
      glow: 'from-blue-500/10 via-blue-500/0 to-transparent',
      hoverGlow: 'group-hover:shadow-[0_20px_40px_rgba(59,130,246,0.12)]',
    },
  };

  const t = themes[colorTheme] || themes.teal;

  const card = (
    <motion.div whileHover={{ y: -6, scale: 1.01 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className={`relative group p-8 bg-card/60 dark:bg-card/40 backdrop-blur-2xl rounded-3xl border ${t.border} ${t.hoverGlow} transition-all duration-500 overflow-hidden flex flex-col justify-between min-h-[280px] h-full shadow-elevation-1 ${className}`}
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${t.glow} opacity-40 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none`} />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div className={`w-14 h-14 rounded-2xl ${t.iconBg} backdrop-blur-md flex items-center justify-center group-hover:scale-110 group-hover:rotate-3 transition-transform duration-300 shadow-sm border`}>
            <Icon className="w-7 h-7" />
          </div>
          {badge && (
            <span className={`px-3 py-1 rounded-full text-xs font-bold border ${t.badgeBg} tracking-wide`}>
              {badge}
            </span>
          )}
        </div>
        <h3 className="text-2xl font-display font-bold text-foreground mb-3 tracking-tight">{title}</h3>
        <p className="text-muted-foreground leading-relaxed text-[15px] md:text-[16px] max-w-[95%]">{description}</p>
      </div>
      {children}
    </motion.div>
  );

  if (link) return <Link to={link} className="block h-full">{card}</Link>;
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

/* ───── FAQ Accordion Item ───── */
const FaqItem = ({ question, answer, isOpen, onToggle, index }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ delay: index * 0.06, duration: 0.4 }}
    className="border border-border/60 hover:border-primary/40 rounded-2xl bg-card/60 dark:bg-card/40 backdrop-blur-xl overflow-hidden transition-all duration-300 shadow-sm"
  >
    <button
      onClick={onToggle}
      className="w-full p-6 text-left flex items-center justify-between gap-4 font-display font-bold text-base md:text-lg text-foreground cursor-pointer focus:outline-none"
    >
      <span className="flex items-center gap-3">
        <span className="w-7 h-7 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center border border-primary/20 flex-shrink-0">
          0{index + 1}
        </span>
        {question}
      </span>
      <motion.div
        animate={{ rotate: isOpen ? 180 : 0 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground flex-shrink-0"
      >
        <ChevronDown className="w-4 h-4" />
      </motion.div>
    </button>
    <motion.div
      initial={false}
      animate={{ height: isOpen ? 'auto' : 0, opacity: isOpen ? 1 : 0 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="overflow-hidden"
    >
      <div className="p-6 pt-0 text-muted-foreground leading-relaxed text-[15px] border-t border-border/30 mt-2">
        {answer}
      </div>
    </motion.div>
  </motion.div>
);

/* ───── FAQ Section Component ───── */
const FaqSection = () => {
  const [openIndex, setOpenIndex] = useState(0);

  const faqs = [
    {
      question: "How does the IoT Smart Pillbox sync with my smartphone?",
      answer: "The IoT Smart Pillbox automatically connects via Bluetooth and Wi-Fi to your Aarogyam mobile app. When you open a compartment, sensor data is instantly logged in real-time to verify dosage accuracy."
    },
    {
      question: "What happens if a patient misses a scheduled medication dose?",
      answer: "If a dose is missed after the scheduled window, Aarogyam triggers multi-channel escalation: starting with subtle app push notifications, followed by WhatsApp alerts, and finally initiating SMS & priority voice calls to both the patient and designated caregivers."
    },
    {
      question: "Can family members or caregivers monitor adherence remotely?",
      answer: "Yes! The Caregiver Portal allows trusted family members or healthcare providers to view live adherence feeds, track weekly completion rates, and receive real-time alerts whenever help is needed."
    },
    {
      question: "How does the AI Risk Score predict adherence issues?",
      answer: "Our machine-learning engine analyzes historical dosing patterns, schedule timing, and behavioral data to detect early signs of non-adherence, allowing proactive caregiver intervention before doses are missed."
    },
    {
      question: "Are my health records and medical data secure & HIPAA compliant?",
      answer: "Absolute privacy is our top priority. All personal health information (PHI) and dosing logs are encrypted in transit and at rest using enterprise-grade AES-256 encryption in full compliance with HIPAA standards."
    },
    {
      question: "Can I export adherence reports to show my physician during checkups?",
      answer: "Yes! You can generate and export comprehensive PDF clinical summaries with one tap. These reports detail weekly/monthly compliance rates, dosage timelines, and trend charts ready for hospital visits."
    }
  ];

  return (
    <section id="faq" className="py-28 px-6 relative bg-transparent">
      <div className="max-w-4xl mx-auto">
        <FadeIn className="text-center mb-16">
          <span className="inline-block py-1.5 px-4 rounded-full bg-primary/10 text-primary font-bold text-xs uppercase tracking-widest mb-4">
            Got Questions? We Have Answers
          </span>
          <h2 className="text-4xl md:text-5xl font-display font-extrabold text-foreground mt-3 tracking-tight">
            Frequently Asked <span className="text-primary bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/70">Questions</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-xl mx-auto mt-4">
            Everything you need to know about the Aarogyam platform, IoT dispenser, and caregiver integration.
          </p>
        </FadeIn>

        <div className="flex flex-col gap-4">
          {faqs.map((faq, i) => (
            <FaqItem
              key={i}
              index={i}
              question={faq.question}
              answer={faq.answer}
              isOpen={openIndex === i}
              onToggle={() => setOpenIndex(openIndex === i ? -1 : i)}
            />
          ))}
        </div>

        {/* Still Have Questions Card */}
        <FadeIn delay={0.4} className="mt-12">
          <div className="p-8 rounded-2xl bg-card/60 backdrop-blur-xl border border-border/60 flex flex-col sm:flex-row items-center justify-between gap-6 text-center sm:text-left shadow-sm">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center border border-primary/20 flex-shrink-0">
                <HelpCircle className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-bold text-foreground text-lg">Still have questions?</h4>
                <p className="text-muted-foreground text-sm">Can't find the answer you're looking for? Reach out to our 24/7 care team.</p>
              </div>
            </div>
            <a href="mailto:support@aarogyam.health" className="flex-shrink-0">
              <Button variant="outline" className="rounded-xl font-bold border-primary/30 text-primary hover:bg-primary/10">
                Contact Support
              </Button>
            </a>
          </div>
        </FadeIn>
      </div>
    </section>
  );
};

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
    { label: 'FAQ', href: '#faq' },
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
    <div className="min-h-screen selection:bg-primary/20 overflow-x-hidden relative">

      {/* ────── HOME PAGE HERO BACKGROUND IMAGE ONLY ────── */}
      <div 
        className="absolute top-0 left-0 right-0 h-[850px] lg:h-[900px] w-full bg-cover bg-right-top bg-no-repeat z-0 pointer-events-none transition-opacity duration-700 opacity-90"
        style={{ backgroundImage: `url(${heroWomanBg})` }}
      />
      {/* Light minimal overlay for hero section */}
      <div className="absolute top-0 left-0 right-0 h-[850px] lg:h-[900px] w-full bg-background/5 z-0 pointer-events-none" />

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
              className="px-4 py-1.5 rounded-full bg-primary/5 text-primary font-bold text-xs flex items-center gap-2 border border-primary/10 shadow-sm"
            >
              <ShieldCheck className="w-4 h-4" />
              Clinical-Grade Smart Medication Companion
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

      {/* ────── ANIMATED TEXT LOOP MARQUEE ────── */}
      <section className="relative overflow-hidden -mt-28 -mb-16 z-30 pointer-events-auto">
        <TextLoop
          text="AAROGYAM ✦ SMART MEDICINE ADHERENCE ✦ REAL-TIME CAREGIVER ALERTS ✦ AI-POWERED RISK ENGINE ✦ NEVER MISS A DOSE"
          shape="wave"
          speed={70}
          direction="forward"
          separator="✦"
          curviness={22}
          fontSize={24}
          fontWeight={800}
          letterSpacing={6}
          uppercase
          color="#0B6E7A"
          ribbon={false}
          ribbonColor="transparent"
          ribbonWidth={0}
          pauseOnHover
        />
      </section>

      {/* ────── CORE PILLARS BANNER ────── */}
      <section id="pillars" className="relative z-10">
        <div className="bg-primary/40 backdrop-blur-xl border-y border-white/20 py-12 shadow-lg">
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { icon: Bell, title: 'Smart Reminders', desc: 'WhatsApp, SMS & Voice Alerts' },
              { icon: ShieldCheck, title: 'IoT Dispenser', desc: 'Automated Compartment Sync' },
              { icon: Users, title: 'Caregiver Portal', desc: 'Real-Time Family Monitoring' },
              { icon: Sparkles, title: 'AI Health Insights', desc: 'Adherence Risk Score Engine' },
            ].map((item, i) => {
              const IconComp = item.icon;
              return (
                <FadeIn key={i} delay={i * 0.1} className="text-center flex flex-col items-center">
                  <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-md flex items-center justify-center text-white mb-3 shadow-sm border border-white/20">
                    <IconComp className="w-6 h-6" />
                  </div>
                  <h3 className="text-base md:text-lg font-display font-bold text-white tracking-tight">
                    {item.title}
                  </h3>
                  <p className="text-white/80 text-xs mt-1 leading-snug">{item.desc}</p>
                </FadeIn>
              );
            })}
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

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Bento Card 1: Smart Reminders (2 Cols) */}
            <BentoCard
              className="lg:col-span-2"
              icon={Bell}
              badge="Multi-Channel"
              title="Smart Reminders"
              description="Automated multi-channel alerts via WhatsApp, SMS, Push, and Voice calls to guarantee 100% adherence."
              colorTheme="teal"
            >
              <div className="mt-6 flex flex-wrap gap-2.5 items-center">
                <div className="bg-teal-500/10 text-teal-700 dark:text-teal-300 text-xs font-semibold py-1.5 px-3.5 rounded-full border border-teal-500/20 flex items-center gap-2">
                  <MessageCircle className="w-3.5 h-3.5 text-teal-600" /> WhatsApp Bot
                </div>
                <div className="bg-teal-500/10 text-teal-700 dark:text-teal-300 text-xs font-semibold py-1.5 px-3.5 rounded-full border border-teal-500/20 flex items-center gap-2">
                  <Smartphone className="w-3.5 h-3.5 text-teal-600" /> Push Notification
                </div>
                <div className="bg-teal-500/10 text-teal-700 dark:text-teal-300 text-xs font-semibold py-1.5 px-3.5 rounded-full border border-teal-500/20 flex items-center gap-2">
                  <Phone className="w-3.5 h-3.5 text-teal-600" /> Voice Call
                </div>
              </div>
            </BentoCard>

            {/* Bento Card 2: IoT Pillbox Hardware (1 Col) */}
            <BentoCard
              className="lg:col-span-1"
              icon={Zap}
              badge="Hardware Sync"
              title="IoT Smart Pillbox"
              description="Direct compartment Bluetooth & Wi-Fi sync for automated dose verification."
              colorTheme="purple"
            >
              <div className="mt-6 pt-4 border-t border-purple-500/10 flex items-center justify-between">
                <span className="text-xs font-semibold text-purple-700 dark:text-purple-300">Hardware Status</span>
                <span className="text-xs font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2.5 py-1 rounded-full border border-purple-500/20 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" /> Connected
                </span>
              </div>
            </BentoCard>

            {/* Bento Card 3: Caregiver Portal (1 Col) */}
            <BentoCard
              className="lg:col-span-1"
              icon={Users}
              badge="Family Care"
              title="Caregiver Portal"
              description="Instant alert feeds for family members when a critical dose is missed."
              colorTheme="rose"
              link="/caregiver"
            >
              <div className="mt-6 pt-4 border-t border-rose-500/10 flex items-center justify-between">
                <span className="text-xs font-semibold text-rose-700 dark:text-rose-300">Family Alert Sync</span>
                <span className="text-xs font-bold text-rose-600 dark:text-rose-400 bg-rose-500/10 px-2.5 py-1 rounded-full border border-rose-500/20">
                  Active Sync
                </span>
              </div>
            </BentoCard>

            {/* Bento Card 4: AI Risk Engine (2 Cols) */}
            <BentoCard
              className="lg:col-span-2"
              icon={Sparkles}
              badge="ML Engine"
              title="AI Adherence Risk Score"
              description="Predictive machine-learning algorithm that calculates adherence risk before doses are missed."
              colorTheme="blue"
            >
              <div className="mt-6 p-4 rounded-2xl bg-blue-500/5 border border-blue-500/15 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <div className="text-xs text-muted-foreground font-semibold">Predicted Patient Risk</div>
                  <div className="text-sm font-bold text-blue-600 dark:text-blue-400">Low Risk — 96% Adherence Confidence</div>
                </div>
                <div className="w-full sm:w-36 h-2 rounded-full bg-blue-500/20 overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full w-[96%]" />
                </div>
              </div>
            </BentoCard>

            {/* Bento Card 5: Consult Doctor (1 Col) */}
            <BentoCard
              className="lg:col-span-1"
              icon={ShieldCheck}
              badge="24/7 Access"
              title="Doctor Consult"
              description="Direct telemedicine connection to verified medical specialists."
              colorTheme="emerald"
              link="/consult-doctors"
            >
              <div className="mt-6 pt-4 border-t border-emerald-500/10 flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">Specialists Online</span>
                <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" /> Available Now
                </span>
              </div>
            </BentoCard>

            {/* Bento Card 6: Adherence Analytics (2 Cols) */}
            <BentoCard
              className="lg:col-span-2"
              icon={BarChart3}
              badge="PDF Export"
              title="Adherence Analytics & Reports"
              description="Clinical-grade health trend visualizations exportable directly for doctor consultations."
              colorTheme="amber"
            >
              <div className="mt-6 flex items-center justify-between pt-4 border-t border-amber-500/10">
                <span className="text-xs font-semibold text-amber-700 dark:text-amber-300">Monthly Clinical Summary</span>
                <span className="text-xs font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
                  Export PDF Report →
                </span>
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

      {/* ────── FAQ SECTION ────── */}
      <FaqSection />

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
