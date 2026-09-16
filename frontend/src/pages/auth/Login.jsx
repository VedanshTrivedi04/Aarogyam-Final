import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ArrowRight, User, Stethoscope, Heart, ShieldCheck, Mail } from 'lucide-react';
import { GoogleLogin } from '@react-oauth/google';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuthStore } from '@/stores/auth.store';
import { authAgent } from '@/agents/auth.agent';
import logoMedicine from '@/assets/logo medicine.png';

const RoleCard = ({ icon: Icon, title, selected, onClick }) => (
  <button
    onClick={onClick}
    className={`flex-1 flex flex-col items-center gap-3 p-4 rounded-xl border transition-all
      ${selected ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border hover:border-primary/50 bg-card'}`}
  >
    <Icon className={`w-6 h-6 ${selected ? 'text-primary' : 'text-muted-foreground'}`} />
    <span className={`text-sm font-bold ${selected ? 'text-primary' : 'text-foreground'}`}>{title}</span>
  </button>
);

const redirectForRole = (role) => {
  if (role === 'DOCTOR') return '/doctor';
  if (role === 'CAREGIVER') return '/caregiver';
  if (role === 'SUPER_ADMIN') return '/super-admin';
  if (role === 'ADMIN') return '/admin';
  return '/dashboard';
};

export default function LoginPage() {
  const location  = useLocation();
  const navigate  = useNavigate();
  const setSession = useAuthStore(s => s.setSession);

  const [role, setRole]           = useState('PATIENT');
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // OTP flow state
  const [useOtp, setUseOtp]         = useState(false);
  const [otpSent, setOtpSent]       = useState(false);
  const [otpCode, setOtpCode]       = useState('');

  // MFA flow state
  const [mfaRequired, setMfaRequired] = useState(location.state?.mfaRequired || false);
  const [mfaCode, setMfaCode]         = useState('');
  const [tempUserId, setTempUserId]   = useState(location.state?.user_id || null);

  // ── helpers ──────────────────────────────────────────────────────────────
  const finishLogin = (res) => {
    setSession({ accessToken: res.access, refreshToken: res.refresh, user: res.user });
    navigate(redirectForRole(res.user.role));
  };

  const toggleOtp = () => {
    setUseOtp(v => !v);
    setPassword('');   // clear password so it can't silently log in
    setOtpSent(false);
    setOtpCode('');
  };

  // ── password login ────────────────────────────────────────────────────────
  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await authAgent.loginWithPassword(email, password);
      if (res.mfa_required) {
        setMfaRequired(true);
        setTempUserId(res.user_id);
        return;
      }
      finishLogin(res);
    } catch (err) {
      alert(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  // ── OTP: step 1 — request OTP ─────────────────────────────────────────────
  const handleRequestOTP = async (e) => {
    e.preventDefault();
    if (!email.trim()) return alert('Please enter your email.');
    setIsLoading(true);
    try {
      await authAgent.requestOTP(email);
      setOtpSent(true);
    } catch (err) {
      alert(err.message || 'Failed to send OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  // ── OTP: step 2 — verify OTP ──────────────────────────────────────────────
  const handleOTPLogin = async (e) => {
    e.preventDefault();
    if (!otpCode.trim()) return alert('Please enter the OTP.');
    setIsLoading(true);
    try {
      const res = await authAgent.loginWithOTP(email, otpCode);
      finishLogin(res);
    } catch (err) {
      alert(err.message || 'Invalid OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  // ── Google ────────────────────────────────────────────────────────────────
  const handleGoogleSuccess = async (credentialResponse) => {
    setIsLoading(true);
    try {
      const res = await authAgent.loginWithGoogle(credentialResponse.credential);
      finishLogin(res);
    } catch (err) {
      alert(err.message || 'Google login failed');
    } finally {
      setIsLoading(false);
    }
  };

  // ── MFA ───────────────────────────────────────────────────────────────────
  const handleMFAVerify = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await authAgent.verifyMFA(tempUserId, mfaCode);
      finishLogin(res);
    } catch (err) {
      alert(err.message || 'MFA Verification failed');
    } finally {
      setIsLoading(false);
    }
  };

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex bg-background">
      {/* Left brand panel */}
      <div className="hidden lg:flex flex-1 bg-primary relative overflow-hidden items-center justify-center p-24">
        <div className="absolute inset-0 opacity-10 pointer-events-none">
          <div className="absolute top-0 left-0 w-96 h-96 bg-white rounded-full -translate-x-1/2 -translate-y-1/2 blur-3xl" />
          <div className="absolute bottom-0 right-0 w-[32rem] h-[32rem] bg-white rounded-full translate-x-1/3 translate-y-1/3 blur-3xl" />
        </div>
        <div className="relative z-10 text-white max-w-lg">
          <div className="w-16 h-16 bg-white/20 backdrop-blur-xl rounded-2xl flex items-center justify-center mb-8">
            <Heart className="w-8 h-8 fill-white" />
          </div>
          <h2 className="text-5xl font-display font-extrabold mb-6 leading-tight">Your Health, <br/>Our Commitment.</h2>
          <p className="text-xl text-primary-foreground/80 leading-relaxed font-sans">
            Join the community of thousands who manage their wellness with clinical precision and warmth.
          </p>
          <div className="mt-12 flex gap-8">
            <div>
              <h4 className="text-3xl font-bold font-display">12M+</h4>
              <p className="text-sm opacity-70 uppercase tracking-widest font-semibold mt-1">Doses Logged</p>
            </div>
            <div className="w-px h-12 bg-white/20" />
            <div>
              <h4 className="text-3xl font-bold font-display">99%</h4>
              <p className="text-sm opacity-70 uppercase tracking-widest font-semibold mt-1">Uptime</p>
            </div>
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-8 md:p-16">
        <div className="w-full max-w-md flex flex-col gap-8">

          <div className="flex flex-col gap-2 text-center lg:text-left">
            <div className="flex lg:hidden items-center justify-center gap-2 mb-4">
              <img src={logoMedicine} alt="Aarogyam Logo" className="w-8 h-8 object-contain" />
              <span className="font-display font-bold text-xl text-primary">Aarogyam</span>
            </div>
            <h1 className="text-4xl font-display font-bold text-foreground">Welcome Back</h1>
            <p className="text-muted-foreground font-sans">Please select your role and sign in to your account.</p>
          </div>

          <div className="flex gap-4">
            <RoleCard icon={User}        title="Patient"   selected={role === 'PATIENT'}   onClick={() => setRole('PATIENT')} />
            <RoleCard icon={ShieldCheck} title="Caregiver" selected={role === 'CAREGIVER'} onClick={() => setRole('CAREGIVER')} />
            <RoleCard icon={Stethoscope} title="Doctor"    selected={role === 'DOCTOR'}    onClick={() => setRole('DOCTOR')} />
          </div>

          {/* ── MFA screen ── */}
          {mfaRequired ? (
            <form onSubmit={handleMFAVerify} className="flex flex-col gap-6">
              <div className="flex flex-col gap-4 text-center">
                <ShieldCheck className="w-12 h-12 text-primary mx-auto" />
                <h2 className="text-2xl font-bold">Two-Factor Authentication</h2>
                <p className="text-muted-foreground">Enter the 6-digit code from your authenticator app.</p>
                <Input
                  label="Verification Code"
                  placeholder="000000"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  maxLength={6}
                  required
                  className="text-center text-2xl tracking-[1em]"
                />
              </div>
              <Button isLoading={isLoading} className="h-14 text-lg">
                Verify & Sign In <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
              <button type="button" onClick={() => setMfaRequired(false)}
                className="text-sm font-semibold text-muted-foreground hover:text-foreground underline">
                Back to Login
              </button>
            </form>

          ) : useOtp ? (
            /* ── OTP flow ── */
            <>
              {!otpSent ? (
                /* Step 1: enter email, request OTP */
                <form onSubmit={handleRequestOTP} className="flex flex-col gap-6">
                  <div className="flex flex-col gap-4 text-center">
                    <Mail className="w-12 h-12 text-primary mx-auto" />
                    <h2 className="text-xl font-bold">Login with OTP</h2>
                    <p className="text-muted-foreground text-sm">We'll send a 6-digit code to your email.</p>
                  </div>
                  <Input
                    label="Email"
                    type="email"
                    placeholder="name@hospital.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                  <Button isLoading={isLoading} className="h-14 text-lg">
                    Send OTP <ArrowRight className="ml-2 w-5 h-5" />
                  </Button>
                  <button type="button" onClick={toggleOtp}
                    className="text-sm font-bold text-primary hover:underline text-center">
                    Login with Password
                  </button>
                </form>
              ) : (
                /* Step 2: enter OTP */
                <form onSubmit={handleOTPLogin} className="flex flex-col gap-6">
                  <div className="flex flex-col gap-4 text-center">
                    <Mail className="w-12 h-12 text-primary mx-auto" />
                    <h2 className="text-xl font-bold">Enter OTP</h2>
                    <p className="text-muted-foreground text-sm">
                      A 6-digit code was sent to <span className="font-semibold text-foreground">{email}</span>
                    </p>
                  </div>
                  <Input
                    label="OTP Code"
                    placeholder="000000"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    maxLength={6}
                    required
                    className="text-center text-2xl tracking-[1em]"
                  />
                  <Button isLoading={isLoading} className="h-14 text-lg">
                    Verify & Sign In <ArrowRight className="ml-2 w-5 h-5" />
                  </Button>
                  <button type="button" onClick={() => setOtpSent(false)}
                    className="text-sm font-semibold text-muted-foreground hover:text-foreground underline text-center">
                    Resend OTP
                  </button>
                </form>
              )}
            </>

          ) : (
            /* ── Password flow ── */
            <>
              <form onSubmit={handlePasswordLogin} className="flex flex-col gap-6">
                <div className="flex flex-col gap-4">
                  <Input
                    label="Email"
                    type="email"
                    placeholder="name@hospital.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                  <Input
                    label="Password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>

                <div className="flex items-center justify-between">
                  <button type="button" onClick={toggleOtp}
                    className="text-sm font-bold text-primary hover:underline">
                    Login with OTP
                  </button>
                  <a href="#" className="text-sm font-semibold text-muted-foreground hover:text-foreground">
                    Forgot Password?
                  </a>
                </div>

                <Button isLoading={isLoading} className="h-14 text-lg">
                  Sign In <ArrowRight className="ml-2 w-5 h-5" />
                </Button>
              </form>

              <div className="flex items-center gap-4">
                <div className="flex-1 h-px bg-border" />
                <span className="text-sm text-muted-foreground font-medium">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>

              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => alert('Google login failed. Please try again.')}
                  useOneTap
                  shape="rectangular"
                  theme="outline"
                  size="large"
                  text="signin_with"
                  width="400"
                />
              </div>
            </>
          )}

          <p className="text-center text-muted-foreground text-sm font-sans">
            Don't have an account?{' '}
            <Link to="/register" className="text-primary font-bold hover:underline">Register Now</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
