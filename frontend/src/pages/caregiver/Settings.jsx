import { useEffect, useMemo, useState } from 'react';
import {
  User, Users, Bell, ShieldCheck, Smartphone, ArrowLeft,
  ChevronRight, MessageCircle, Clock, Save, LogOut, Loader2,
  Crown, X, Zap, Star, CreditCard, Mail, Download,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useAuthStore } from '@/stores/auth.store';
import { useCaregiverDevices, useDeviceDetail, useUpdateDeviceDetail } from '@/hooks/useIoT';
import {
  useCurrentSubscription, useCancelSubscription,
  useSubscriptionPlans, useUpgradeSubscription,
  useSubscriptionInvoices, useEmailInvoice,
} from '@/hooks/useSettings';

const SettingItem = ({ icon: Icon, title, description }) => (
  <button className="w-full flex items-center justify-between p-5 bg-card rounded-[1.5rem] border border-border/50 hover:border-primary/30 hover:bg-secondary/20 transition-all group">
    <div className="flex items-center gap-4">
      <div className="w-11 h-11 rounded-xl bg-muted flex items-center justify-center text-muted-foreground group-hover:bg-primary group-hover:text-white transition-all">
        <Icon className="w-5 h-5" />
      </div>
      <div className="text-left">
        <h4 className="font-bold text-foreground">{title}</h4>
        <p className="text-xs text-muted-foreground font-medium">{description}</p>
      </div>
    </div>
    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
  </button>
);

export default function CaregiverSettings() {
  const navigate = useNavigate();
  const { user, clearSession } = useAuthStore();
  const { data: devices = [] } = useCaregiverDevices();
  const { data: currentPlan, isLoading: planLoading } = useCurrentSubscription();
  const { data: plans = [], isLoading: plansLoading } = useSubscriptionPlans();
  const { data: invoices = [] }                        = useSubscriptionInvoices();
  const cancelSubscription  = useCancelSubscription();
  const upgradeSubscription = useUpgradeSubscription();
  const emailInvoice        = useEmailInvoice();
  const [payingPlanId, setPayingPlanId]   = useState(null);
  const [emailingInvoiceId, setEmailingId] = useState(null);
  const [subToast, setSubToast]            = useState(null);

  const PLAN_ICONS = { basic: Star, pro: Zap, ultimate: Crown };

  async function handleUpgrade(planId) {
    setPayingPlanId(planId);
    try {
      await upgradeSubscription.mutateAsync(planId);
      setSubToast({ msg: 'Payment successful! Subscription activated.', ok: true });
    } catch (err) {
      const msg = err?.message || '';
      if (!msg.includes('cancelled')) setSubToast({ msg: msg || 'Payment failed.', ok: false });
    } finally {
      setPayingPlanId(null);
      setTimeout(() => setSubToast(null), 3500);
    }
  }

  async function handleEmailInvoice(invoiceId) {
    setEmailingId(invoiceId);
    try {
      await emailInvoice.mutateAsync(invoiceId);
      setSubToast({ msg: 'Invoice emailed successfully!', ok: true });
    } catch (err) {
      setSubToast({ msg: err?.message || 'Failed to send invoice.', ok: false });
    } finally {
      setEmailingId(null);
      setTimeout(() => setSubToast(null), 3500);
    }
  }
  const activeDevice = devices[0];
  const { data: deviceDetail } = useDeviceDetail(activeDevice?.id);
  const updateDeviceDetail = useUpdateDeviceDetail();

  const [formState, setFormState] = useState({
    device_name: '', caregiver_name: '', caregiver_phone: '', caregiver_email: '', chemist_name: '', chemist_phone: '',
  });

  useEffect(() => {
    if (deviceDetail) {
      setFormState({
        device_name: deviceDetail.device_name || '',
        caregiver_name: deviceDetail.caregiver_name || '',
        caregiver_phone: deviceDetail.caregiver_phone || '',
        caregiver_email: deviceDetail.caregiver_email || '',
        chemist_name: deviceDetail.chemist_name || '',
        chemist_phone: deviceDetail.chemist_phone || '',
      });
    }
  }, [deviceDetail]);

  const systemStatus = useMemo(() => ([
    { label: 'Cloud Sync', value: activeDevice ? (activeDevice.is_online ? 'Active' : 'Offline') : 'No device', icon: ShieldCheck, color: activeDevice?.is_online ? 'text-success' : 'text-amber-500' },
    { label: 'Device Battery', value: activeDevice?.battery_level != null ? `${activeDevice.battery_level}%` : '--', icon: Clock, color: 'text-primary' },
    { label: 'Firmware', value: activeDevice?.firmware_version || '--', icon: MessageCircle, color: 'text-primary' },
  ]), [activeDevice]);

  const handleSave = async () => {
    if (!activeDevice) return;
    await updateDeviceDetail.mutateAsync({ deviceId: activeDevice.id, data: formState });
  };

  return (
    <div className="flex flex-col gap-8 py-4 max-w-4xl mx-auto">
      <div className="flex flex-col gap-6">
        <button onClick={() => navigate('/caregiver/home')} className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors w-fit">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em]">Dashboard</span>
        </button>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <h2 className="text-3xl font-display font-extrabold text-foreground tracking-tight">Caregiver Settings</h2>
          <Button className="h-12 px-8 rounded-xl shadow-lg font-bold" onClick={handleSave} disabled={updateDeviceDetail.isPending || !activeDevice}>
            {updateDeviceDetail.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />} Save Preferences
          </Button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 flex flex-col gap-4">
          <h3 className="text-sm font-black uppercase tracking-widest text-muted-foreground ml-2">Clinical Management</h3>
          <SettingItem icon={Users} title="Linked Patients" description="Patient list and analytics are driven by the backend caregiver cohort." />
          <SettingItem icon={Bell} title="Alert Preferences" description="Live alerts now come from patient and IoT anomaly streams." />
          <SettingItem icon={ShieldCheck} title="Emergency Escalation" description="Remote unlock and fill-mode commands are sent to the backend IoT queue." />

          <h3 className="text-sm font-black uppercase tracking-widest text-muted-foreground ml-2 mt-4">Account & Device</h3>
          <SettingItem icon={User} title="Profile Information" description={user?.full_name || user?.email || 'Current signed-in account'} />
          <SettingItem icon={Smartphone} title="Device Linkage" description={activeDevice?.device_name || 'No dispenser linked'} />

          <h3 className="text-sm font-black uppercase tracking-widest text-muted-foreground ml-2 mt-4">Subscription</h3>

          {/* Toast */}
          {subToast && (
            <div className={`flex items-center gap-2 px-4 py-3 rounded-2xl text-sm font-bold text-white ${subToast.ok ? 'bg-emerald-500' : 'bg-destructive'}`}>
              {subToast.ok ? <ShieldCheck className="w-4 h-4" /> : <X className="w-4 h-4" />} {subToast.msg}
            </div>
          )}

          {/* Current Plan */}
          <div className="rounded-[1.5rem] bg-card border border-border/50 p-6 flex flex-col gap-3">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                <Crown className="w-4 h-4" />
              </div>
              <h4 className="font-bold text-base">Current Plan</h4>
            </div>
            {planLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
            ) : !currentPlan ? (
              <p className="text-sm text-muted-foreground">No active subscription. Choose a plan below.</p>
            ) : (
              <>
                <div className="flex items-center flex-wrap gap-3">
                  <span className="px-4 py-2 rounded-xl bg-primary/10 text-primary font-black text-lg">{currentPlan.plan?.name}</span>
                  <span className={`text-xs font-bold px-3 py-1 rounded-full ${currentPlan.status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-yellow-500/10 text-yellow-600'}`}>{currentPlan.status}</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  ₹{currentPlan.plan?.price_monthly}/mo · Expires: {currentPlan.expires_at ? new Date(currentPlan.expires_at).toLocaleDateString('en-IN') : 'Never'}
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-xl bg-secondary/40 text-center">
                    <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Max Medications</p>
                    <p className="text-lg font-black text-foreground mt-1">{currentPlan.plan?.max_medications ?? '—'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-secondary/40 text-center">
                    <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Max Caregivers</p>
                    <p className="text-lg font-black text-foreground mt-1">{currentPlan.plan?.max_caregivers ?? '—'}</p>
                  </div>
                </div>
                {currentPlan.auto_renew && (
                  <button
                    disabled={cancelSubscription.isPending}
                    onClick={async () => {
                      if (!window.confirm('Disable auto-renew?')) return;
                      await cancelSubscription.mutateAsync();
                    }}
                    className="flex items-center gap-2 text-sm font-bold text-destructive border border-destructive/30 w-fit px-4 py-2 rounded-xl hover:bg-destructive/5 transition-all"
                  >
                    {cancelSubscription.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />} Disable Auto-Renew
                  </button>
                )}
              </>
            )}
          </div>

          {/* Available Plans */}
          <div className="rounded-[1.5rem] bg-card border border-border/50 p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary"><Zap className="w-4 h-4" /></div>
              <h4 className="font-bold text-base">Upgrade Plan</h4>
            </div>
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              Secured by Razorpay. Test card: <strong>4111 1111 1111 1111</strong>, any future expiry &amp; CVV.
            </p>
            {plansLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading plans…</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {plans.map(plan => {
                  const isCurrent = currentPlan?.plan?.id === plan.id;
                  const isPaying  = payingPlanId === plan.id;
                  const Icon      = PLAN_ICONS[plan.slug] || Star;
                  return (
                    <div key={plan.id} className={`relative p-4 rounded-2xl border-2 flex flex-col gap-2 transition-all ${isCurrent ? 'border-primary bg-primary/5' : 'border-border/50 hover:border-primary/40 bg-card'}`}>
                      {isCurrent && <span className="absolute top-2 right-2 text-[9px] bg-primary text-primary-foreground px-2 py-0.5 rounded-full font-black">CURRENT</span>}
                      <div className="flex items-center gap-2">
                        <Icon className={`w-4 h-4 ${isCurrent ? 'text-primary' : 'text-muted-foreground'}`} />
                        <h5 className="font-bold text-sm">{plan.name}</h5>
                      </div>
                      <p className="text-xl font-black">₹{plan.price_monthly}<span className="text-xs font-medium text-muted-foreground">/mo</span></p>
                      <ul className="text-xs text-muted-foreground space-y-0.5 flex-1">
                        <li>✓ {plan.max_medications} medications</li>
                        <li>✓ {plan.max_caregivers} caregivers</li>
                      </ul>
                      {!isCurrent && (
                        <button
                          onClick={() => handleUpgrade(plan.id)}
                          disabled={!!payingPlanId}
                          className="flex items-center justify-center gap-1.5 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition-all disabled:opacity-60"
                        >
                          {isPaying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CreditCard className="w-3.5 h-3.5" />}
                          {isPaying ? 'Processing…' : 'Pay & Upgrade'}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Invoice History */}
          {invoices.length > 0 && (
            <div className="rounded-[1.5rem] bg-card border border-border/50 p-6 flex flex-col gap-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary"><CreditCard className="w-4 h-4" /></div>
                <h4 className="font-bold text-base">Invoice History</h4>
              </div>
              {invoices.slice(0, 6).map(inv => (
                <div key={inv.id} className="flex items-center justify-between p-3 rounded-xl bg-secondary/30">
                  <div>
                    <p className="font-bold text-sm">₹{inv.amount} {inv.currency}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(inv.created_at).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })} ·{' '}
                      <span className={inv.status === 'PAID' ? 'text-emerald-600 font-bold' : 'text-yellow-600 font-bold'}>{inv.status}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      title="Email this invoice"
                      disabled={emailingInvoiceId === inv.id}
                      onClick={() => handleEmailInvoice(inv.id)}
                      className="p-2 rounded-lg hover:bg-primary/10 text-primary transition-all disabled:opacity-50"
                    >
                      {emailingInvoiceId === inv.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                    </button>
                    <a
                      href={import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/subscriptions/invoices/${inv.id}/download/` : `/api/v1/subscriptions/invoices/${inv.id}/download/`}
                      target="_blank" rel="noreferrer"
                      className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-all"
                      title="Download PDF"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          <Button variant="ghost" className="mt-8 text-destructive hover:bg-destructive/10 h-14 rounded-2xl font-black uppercase tracking-[0.2em] text-xs" onClick={() => { clearSession(); navigate('/login'); }}>
            <LogOut className="w-4 h-4 mr-2" /> Secure Sign Out
          </Button>
        </div>

        <div className="flex flex-col gap-6">
          <Card className="rounded-[2.5rem] bg-primary text-white border-none shadow-xl shadow-primary/20">
            <CardContent className="p-8 flex flex-col items-center text-center gap-4">
              <div className="w-20 h-20 rounded-[2rem] bg-white/20 backdrop-blur-xl flex items-center justify-center text-3xl font-black">
                {(user?.full_name || 'AS').slice(0, 2).toUpperCase()}
              </div>
              <div>
                <h4 className="text-xl font-display font-black">{user?.full_name || 'Clinical Caregiver'}</h4>
                <p className="text-[10px] font-black uppercase tracking-widest opacity-70">{user?.email || 'Signed-in account'}</p>
              </div>
              <Badge variant="success" className="bg-white/20 text-white border-none">Live Session ✓</Badge>
            </CardContent>
          </Card>

          <Card className="rounded-[2.5rem] border-dashed border-border/60">
            <CardHeader>
              <h4 className="font-display font-bold text-lg">System Status</h4>
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-4">
              {systemStatus.map((status) => (
                <div key={status.label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <status.icon className={`w-4 h-4 ${status.color}`} />
                    <span className="text-xs font-bold text-muted-foreground">{status.label}</span>
                  </div>
                  <span className="text-xs font-black text-foreground">{status.value}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="rounded-[2.5rem] border-border/50">
            <CardContent className="p-6 space-y-4">
              <h4 className="font-display font-bold text-lg">Device Contacts</h4>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Device Name</p>
                  <input value={formState.device_name} onChange={(event) => setFormState((current) => ({ ...current, device_name: event.target.value }))} className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3" placeholder="Device name" />
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Caregiver Phone</p>
                  <input value={formState.caregiver_phone} onChange={(event) => setFormState((current) => ({ ...current, caregiver_phone: event.target.value }))} className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3" placeholder="Phone" />
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Caregiver Email</p>
                  <input value={formState.caregiver_email} onChange={(event) => setFormState((current) => ({ ...current, caregiver_email: event.target.value }))} className="mt-2 w-full rounded-xl border border-border/60 bg-background px-4 py-3" placeholder="Email" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
