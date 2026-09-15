import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User, Mail, Phone, Calendar, Droplets, Globe,
  Stethoscope, Building2, ShieldCheck, Camera, Check, X,
  Loader2, Edit3, Save, AlertCircle, BadgeCheck, Lock, KeyRound,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useAuthStore } from '@/stores/auth.store';
import {
  useUserProfile, useUpdateUserProfile, useUploadAvatar,
  usePatientProfile, useUpdatePatientProfile,
} from '@/hooks/useUserProfile';
import { useChangePassword } from '@/hooks/useSettings';
import { useDoctorProfile } from '@/hooks/useDoctor';

const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
const ALLOWED_AVATAR_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

/* ── Toast ───────────────────────────────────────────────────────────────── */
function Toast({ msg, ok }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className={`fixed top-6 right-6 z-[999] flex items-center gap-3 px-5 py-3 rounded-2xl shadow-2xl font-bold text-sm text-white ${ok ? 'bg-emerald-500' : 'bg-red-500'}`}
    >
      {ok ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
      {msg}
    </motion.div>
  );
}

/* ── Field ────────────────────────────────────────────────────────────────── */
function Field({ label, icon: Icon, value, onChange, type = 'text', readOnly = false, placeholder = '' }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5" />}
        {label}
      </label>
      <input
        type={type}
        value={value ?? ''}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
        readOnly={readOnly}
        placeholder={placeholder || label}
        className={`px-4 py-3 rounded-xl border text-sm font-medium outline-none transition-all
          ${readOnly
            ? 'bg-muted/30 border-border/40 text-muted-foreground cursor-not-allowed'
            : 'bg-background border-border focus:border-primary/60 focus:ring-2 focus:ring-primary/15'
          }`}
      />
    </div>
  );
}

/* ── SelectField ─────────────────────────────────────────────────────────── */
function SelectField({ label, icon: Icon, value, onChange, options }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5" />}
        {label}
      </label>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="px-4 py-3 rounded-xl border border-border bg-background text-sm font-medium outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/15 transition-all"
      >
        {options.map(({ label: l, value: v }) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </div>
  );
}

/* ── SectionCard ─────────────────────────────────────────────────────────── */
function SectionCard({ title, icon: Icon, children }) {
  return (
    <Card className="rounded-[2rem] border-border/60 shadow-sm">
      <CardHeader className="flex flex-row items-center gap-3 p-6 pb-0">
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
          <Icon className="w-4.5 h-4.5" />
        </div>
        <h3 className="font-display font-bold text-lg">{title}</h3>
      </CardHeader>
      <CardContent className="p-6">{children}</CardContent>
    </Card>
  );
}

/* ── Avatar ──────────────────────────────────────────────────────────────── */
function AvatarUploader({ initials, photoUrl, onUpload, isUploading }) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (file) onUpload(file);
  };

  return (
    <div className="relative">
      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_AVATAR_TYPES.join(',')}
        className="hidden"
        onChange={handleFileChange}
      />
      <div
        className="relative w-24 h-24 rounded-[2rem] bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white font-display font-black text-3xl shadow-xl cursor-pointer overflow-hidden hover:opacity-90 transition-opacity"
        onClick={() => !isUploading && fileInputRef.current?.click()}
      >
        {photoUrl ? (
          <img src={photoUrl} alt="Profile" className="w-full h-full object-cover" />
        ) : (
          initials
        )}
        {isUploading && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-white animate-spin" />
          </div>
        )}
        <div className="absolute -bottom-2 -right-2 w-8 h-8 rounded-full bg-card border-2 border-border shadow-lg flex items-center justify-center">
          <Camera className="w-4 h-4 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════════
   MAIN
═══════════════════════════════════════════════════════════════════════════ */
export default function ProfilePage() {
  const { user } = useAuthStore();
  const role = user?.role ?? 'PATIENT';

  const [toast, setToast] = useState(null);

  // ── Base user profile ──
  const { data: profile, isLoading: loadingProfile } = useUserProfile();
  const updateUser = useUpdateUserProfile();
  const uploadAvatar = useUploadAvatar();
  const [userForm, setUserForm] = useState({
    first_name: '', last_name: '', phone_number: '', email: '',
  });

  useEffect(() => {
    if (profile) {
      const names = (profile.full_name || '').trim().split(' ');
      const fName = names[0] || '';
      const lName = names.slice(1).join(' ') || '';

      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUserForm({
        first_name:   profile.first_name   ?? profile.firstName ?? fName ?? '',
        last_name:    profile.last_name    ?? profile.lastName  ?? lName ?? '',
        phone_number: profile.phone_number ?? '',
        email:        profile.email ?? user?.email ?? '',
      });
    }
  }, [profile, user]);

  // ── Patient profile ──
  const isPatient  = role === 'PATIENT';
  const isDoctor   = role === 'DOCTOR';
  const isCaregiver = role === 'CAREGIVER';

  const { data: patientData, isLoading: loadingPatient } = usePatientProfile();
  const updatePatient = useUpdatePatientProfile();
  const [patientForm, setPatientForm] = useState({
    date_of_birth: '', gender: 'NS', blood_group: '', timezone: 'Asia/Kolkata',
  });

  useEffect(() => {
    if (patientData) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPatientForm({
        date_of_birth: patientData.date_of_birth ?? '',
        gender:        patientData.gender        ?? 'NS',
        blood_group:   patientData.blood_group   ?? '',
        timezone:      patientData.timezone      ?? 'Asia/Kolkata',
      });
    }
  }, [patientData]);

  // ── Doctor profile ──
  const { data: doctorProfile, isLoading: loadingDoctor } = useDoctorProfile();

  // ── Password change ──
  const changePassword = useChangePassword();
  const [pwForm, setPwForm] = useState({ old_password: '', new_password: '', confirm_password: '' });
  const [pwError, setPwError] = useState('');

  // ── Helpers ──
  function showToast(msg, ok) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleAvatarUpload(file) {
    if (!ALLOWED_AVATAR_TYPES.includes(file.type)) {
      showToast('Only JPEG, PNG, WEBP, or GIF images are allowed.', false);
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      showToast('Image must be 5MB or smaller.', false);
      return;
    }
    try {
      await uploadAvatar.mutateAsync(file);
      showToast('Profile photo updated!', true);
    } catch (err) {
      showToast(err?.message || 'Failed to upload photo.', false);
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setPwError('');
    if (pwForm.new_password.length < 8) {
      setPwError('New password must be at least 8 characters.');
      return;
    }
    if (pwForm.new_password !== pwForm.confirm_password) {
      setPwError('New password and confirmation do not match.');
      return;
    }
    try {
      await changePassword.mutateAsync({
        old_password: pwForm.old_password,
        new_password: pwForm.new_password,
      });
      setPwForm({ old_password: '', new_password: '', confirm_password: '' });
      showToast('Password changed! Other sessions have been signed out.', true);
    } catch (err) {
      setPwError(err?.message || 'Failed to change password.');
    }
  }

  const isLoading = loadingProfile || (isPatient && loadingPatient) || (isDoctor && loadingDoctor);

  const initials = [
    (userForm.first_name || profile?.first_name || profile?.firstName || '?')[0],
    (userForm.last_name  || profile?.last_name  || profile?.lastName  || '')[0],
  ].filter(Boolean).join('').toUpperCase() || '??';

  const email = profile?.email ?? user?.email ?? '';

  // ── Save personal info ──
  async function handleSavePersonal(e) {
    e.preventDefault();
    try {
      const fullName = `${userForm.first_name.trim()} ${userForm.last_name.trim()}`.trim();
      await updateUser.mutateAsync({
        full_name:    fullName,
        first_name:   userForm.first_name.trim(),
        last_name:    userForm.last_name.trim(),
        phone_number: userForm.phone_number.trim() || null,
        email:        userForm.email.trim(),
      });
      showToast('Profile updated!', true);
    } catch (err) {
      showToast(err?.message || 'Update failed.', false);
    }
  }

  // ── Save medical info (patient only) ──
  async function handleSaveMedical(e) {
    e.preventDefault();
    try {
      await updatePatient.mutateAsync({
        date_of_birth: patientForm.date_of_birth || null,
        gender:        patientForm.gender,
        blood_group:   patientForm.blood_group || null,
        timezone:      patientForm.timezone,
      });
      showToast('Medical info updated!', true);
    } catch (err) {
      showToast(err?.message || 'Update failed.', false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        <span className="font-medium">Loading profile…</span>
      </div>
    );
  }

  const roleLabel = { PATIENT: 'Patient', CAREGIVER: 'Caregiver', DOCTOR: 'Doctor' }[role] ?? role;
  const roleColor = { PATIENT: 'bg-primary/10 text-primary', CAREGIVER: 'bg-emerald-500/10 text-emerald-600', DOCTOR: 'bg-violet-500/10 text-violet-600' }[role] ?? 'bg-muted text-muted-foreground';

  return (
    <div className="flex flex-col gap-8 py-4 max-w-3xl">
      <AnimatePresence>{toast && <Toast msg={toast.msg} ok={toast.ok} />}</AnimatePresence>

      {/* ── Page header ── */}
      <div>
        <h1 className="text-3xl font-display font-extrabold tracking-tight flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-primary/10 flex items-center justify-center">
            <User className="w-5 h-5 text-primary" />
          </div>
          My Profile
        </h1>
        <p className="text-muted-foreground font-medium mt-1">Manage your personal details and preferences.</p>
      </div>

      {/* ── Avatar + Identity card ── */}
      <Card className="rounded-[2rem] overflow-hidden border-border/60">
        <div className="h-24 bg-gradient-to-r from-primary/20 via-primary/10 to-transparent" />
        <CardContent className="px-8 pb-8 -mt-12">
          <div className="flex flex-col sm:flex-row items-start sm:items-end gap-6">
            <AvatarUploader
              initials={initials}
              photoUrl={profile?.profile_photo_url}
              onUpload={handleAvatarUpload}
              isUploading={uploadAvatar.isPending}
            />
            <div className="flex-1 pb-2">
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-2xl font-display font-extrabold text-foreground">
                  {userForm.first_name || profile?.firstName || 'Your'} {userForm.last_name || profile?.lastName || 'Name'}
                </h2>
                <span className={`text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full ${roleColor}`}>
                  {roleLabel}
                </span>
                {isPatient && patientData?.patient_code && (
                  <span className="text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full bg-muted text-muted-foreground">
                    {patientData.patient_code}
                  </span>
                )}
                {isDoctor && doctorProfile?.is_verified && (
                  <Badge className="h-5 px-2 text-[9px] bg-emerald-500/10 text-emerald-600 border-none flex items-center gap-1">
                    <BadgeCheck className="w-3 h-3" /> Verified
                  </Badge>
                )}
              </div>
              <p className="text-muted-foreground text-sm font-medium mt-1 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5" />
                {email || 'No email on file'}
              </p>
              {userForm.phone_number && (
                <p className="text-muted-foreground text-sm font-medium mt-0.5 flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5" />
                  {userForm.phone_number}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Personal Information ── */}
      <SectionCard title="Personal Information" icon={Edit3}>
        <form onSubmit={handleSavePersonal} className="flex flex-col gap-5">
          <div className="grid sm:grid-cols-2 gap-4">
            <Field
              label="First Name"
              icon={User}
              value={userForm.first_name}
              onChange={(v) => setUserForm(f => ({ ...f, first_name: v }))}
              placeholder="Enter first name"
            />
            <Field
              label="Last Name"
              icon={User}
              value={userForm.last_name}
              onChange={(v) => setUserForm(f => ({ ...f, last_name: v }))}
              placeholder="Enter last name"
            />
          </div>
          <Field
            label="Email Address"
            icon={Mail}
            value={userForm.email}
            onChange={(v) => setUserForm(f => ({ ...f, email: v }))}
            placeholder="Email address"
            type="email"
          />
          <Field
            label="Phone Number"
            icon={Phone}
            value={userForm.phone_number}
            onChange={(v) => setUserForm(f => ({ ...f, phone_number: v }))}
            placeholder="+91 XXXXX XXXXX"
            type="tel"
          />
          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              disabled={updateUser.isPending}
              className="h-11 px-8 rounded-xl font-bold shadow-lg shadow-primary/20"
            >
              {updateUser.isPending
                ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</>
                : <><Save className="w-4 h-4 mr-2" />Save Changes</>
              }
            </Button>
          </div>
        </form>
      </SectionCard>

      {/* ── Security ── */}
      <SectionCard title="Security" icon={Lock}>
        <form onSubmit={handleChangePassword} className="flex flex-col gap-5">
          <Field
            label="Current Password"
            icon={Lock}
            type="password"
            value={pwForm.old_password}
            onChange={(v) => setPwForm(f => ({ ...f, old_password: v }))}
            placeholder="Enter current password"
          />
          <div className="grid sm:grid-cols-2 gap-4">
            <Field
              label="New Password"
              icon={KeyRound}
              type="password"
              value={pwForm.new_password}
              onChange={(v) => setPwForm(f => ({ ...f, new_password: v }))}
              placeholder="At least 8 characters"
            />
            <Field
              label="Confirm New Password"
              icon={KeyRound}
              type="password"
              value={pwForm.confirm_password}
              onChange={(v) => setPwForm(f => ({ ...f, confirm_password: v }))}
              placeholder="Re-enter new password"
            />
          </div>

          {pwError && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-destructive/10 text-destructive text-sm font-semibold">
              <AlertCircle className="w-4 h-4 shrink-0" /> {pwError}
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              disabled={changePassword.isPending || !pwForm.old_password || !pwForm.new_password || !pwForm.confirm_password}
              className="h-11 px-8 rounded-xl font-bold shadow-lg shadow-primary/20"
            >
              {changePassword.isPending
                ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Updating…</>
                : <><Save className="w-4 h-4 mr-2" />Change Password</>
              }
            </Button>
          </div>
        </form>
      </SectionCard>

      {/* ── Medical Information (Patient only) ── */}
      {isPatient && (
        <SectionCard title="Medical Information" icon={Stethoscope}>
          <form onSubmit={handleSaveMedical} className="flex flex-col gap-5">
            <div className="grid sm:grid-cols-2 gap-4">
              <Field
                label="Date of Birth"
                icon={Calendar}
                type="date"
                value={patientForm.date_of_birth}
                onChange={(v) => setPatientForm(f => ({ ...f, date_of_birth: v }))}
              />
              <SelectField
                label="Blood Group"
                icon={Droplets}
                value={patientForm.blood_group}
                onChange={(v) => setPatientForm(f => ({ ...f, blood_group: v }))}
                options={[
                  { label: 'Not specified', value: '' },
                  ...['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(g => ({ label: g, value: g })),
                ]}
              />
              <SelectField
                label="Gender"
                icon={User}
                value={patientForm.gender}
                onChange={(v) => setPatientForm(f => ({ ...f, gender: v }))}
                options={[
                  { label: 'Prefer not to say', value: 'NS' },
                  { label: 'Male', value: 'M' },
                  { label: 'Female', value: 'F' },
                  { label: 'Other', value: 'O' },
                ]}
              />
              <SelectField
                label="Timezone"
                icon={Globe}
                value={patientForm.timezone}
                onChange={(v) => setPatientForm(f => ({ ...f, timezone: v }))}
                options={[
                  { label: 'India (IST)', value: 'Asia/Kolkata' },
                  { label: 'UTC', value: 'UTC' },
                  { label: 'US Eastern', value: 'America/New_York' },
                  { label: 'US Pacific', value: 'America/Los_Angeles' },
                  { label: 'London (GMT)', value: 'Europe/London' },
                  { label: 'Dubai (GST)', value: 'Asia/Dubai' },
                  { label: 'Singapore', value: 'Asia/Singapore' },
                ]}
              />
            </div>

            {patientData?.patient_code && (
              <div className="flex items-center gap-3 p-4 bg-muted/30 rounded-2xl">
                <ShieldCheck className="w-5 h-5 text-primary shrink-0" />
                <div>
                  <p className="text-xs font-black uppercase tracking-widest text-muted-foreground">Your Patient Code</p>
                  <p className="font-bold text-foreground text-lg tracking-widest">{patientData.patient_code}</p>
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <Button
                type="submit"
                disabled={updatePatient.isPending}
                className="h-11 px-8 rounded-xl font-bold shadow-lg shadow-primary/20"
              >
                {updatePatient.isPending
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</>
                  : <><Save className="w-4 h-4 mr-2" />Save Medical Info</>
                }
              </Button>
            </div>
          </form>
        </SectionCard>
      )}

      {/* ── Professional Information (Doctor only) ── */}
      {isDoctor && (
        <SectionCard title="Professional Information" icon={Stethoscope}>
          <div className="flex flex-col gap-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <Field
                label="Specialization"
                icon={Stethoscope}
                value={doctorProfile?.specialization ?? ''}
                readOnly
              />
              <Field
                label="Registration Number"
                icon={BadgeCheck}
                value={doctorProfile?.registration_number ?? ''}
                readOnly
              />
              <Field
                label="Hospital / Clinic"
                icon={Building2}
                value={doctorProfile?.hospital_name ?? ''}
                readOnly
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                  Verification Status
                </label>
                <div className={`px-4 py-3 rounded-xl border text-sm font-bold flex items-center gap-2 ${doctorProfile?.is_verified ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600' : 'bg-amber-500/10 border-amber-500/30 text-amber-600'}`}>
                  {doctorProfile?.is_verified ? <BadgeCheck className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                  {doctorProfile?.is_verified ? 'Verified Doctor' : 'Pending Verification'}
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground font-medium">
              To update your professional details, please contact MedAdhere support.
            </p>
          </div>
        </SectionCard>
      )}

      {/* ── Caregiver badge ── */}
      {isCaregiver && (
        <SectionCard title="Caregiver Role" icon={ShieldCheck}>
          <div className="flex items-center gap-4 p-4 bg-emerald-500/5 rounded-2xl border border-emerald-500/20">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6 text-emerald-600" />
            </div>
            <div>
              <p className="font-bold text-foreground">Active Caregiver</p>
              <p className="text-sm text-muted-foreground font-medium">
                You are authorized to monitor linked patients, manage their IoT devices, and receive dose alerts.
              </p>
            </div>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
