import { useState } from 'react';
import { 
  Users, 
  AlertCircle, 
  Search, 
  MessageSquare, 
  Pill, 
  ChevronRight, 
  Activity,
  ArrowUpRight,
  Filter,
  Plus,
  UserCircle,
  Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useDoctorPatients, useDoctorPatientsData, useDoctorProfile } from '@/hooks/useDoctor';
import { useSetAvailability } from '@/hooks/useDoctorConsultation';

function AvailabilityToggle() {
  const { data: profile } = useDoctorProfile();
  const setAvailability = useSetAvailability();
  const isAvailable = profile?.is_available ?? true;

  return (
    <button
      onClick={() => setAvailability.mutate(!isAvailable)}
      disabled={setAvailability.isPending}
      title={isAvailable ? 'Patients can request calls/consults' : 'You will not receive new calls or consult requests'}
      className={`flex items-center gap-2.5 h-12 px-4 rounded-xl border transition-colors ${
        isAvailable ? 'bg-success/10 border-success/30 text-success' : 'bg-muted border-border text-muted-foreground'
      }`}
    >
      <span className={`w-2.5 h-2.5 rounded-full ${isAvailable ? 'bg-success animate-pulse' : 'bg-muted-foreground/50'}`} />
      <span className="text-xs font-black uppercase tracking-wider">
        {isAvailable ? 'Accepting Calls' : 'Unavailable'}
      </span>
    </button>
  );
}

const PatientRow = ({ patient, data = {}, onClick }) => {
  const { adherence, alerts, isLoading } = data;
  const pct = adherence?.adherence_pct ?? 0;
  
  return (
    <tr className="hover:bg-muted/30 transition-colors cursor-pointer group" onClick={onClick}>
      <td className="px-6 py-5">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold">
            {(patient.name ?? '?')[0]}
          </div>
          <div>
            <h4 className="font-bold text-foreground">{patient.name}</h4>
            <p className="text-xs text-muted-foreground font-medium capitalize">{patient.status} • {patient.permission || 'view only'}</p>
          </div>
        </div>
      </td>
      <td className="px-6 py-5 text-center">
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground mx-auto" />
        ) : (
          <div className="flex flex-col items-center">
            <span className={`text-sm font-bold ${pct < 80 ? 'text-destructive' : 'text-success'}`}>
              {pct.toFixed(0)}%
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">
              {adherence?.taken ?? 0} / {adherence?.total_scheduled ?? 0} doses
            </span>
          </div>
        )}
      </td>
      <td className="px-6 py-5 text-center">
        <Badge variant={patient.status === 'active' ? 'success' : 'warning'} className="uppercase">
          {patient.status}
        </Badge>
      </td>
      <td className="px-6 py-5 text-right">
        <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 rounded-full bg-secondary"><MessageSquare className="w-4 h-4 text-primary" /></Button>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 rounded-full bg-secondary"><Pill className="w-4 h-4 text-primary" /></Button>
          <ChevronRight className="w-5 h-5 text-muted-foreground" />
        </div>
      </td>
    </tr>
  );
};

export default function DoctorPortal() {
  const [search, setSearch] = useState('');
  const { data: patients = [], isLoading, isError } = useDoctorPatients();
  const patientsData = useDoctorPatientsData(patients);

  const filtered = patients.filter(p =>
    !search || p.name.toLowerCase().includes(search.toLowerCase())
  );

  // Compute total adherence
  let totalPct = 0;
  let adherenceCount = 0;
  
  // Aggregate alerts
  const allAlerts = [];

  patients.forEach(p => {
    const data = patientsData[p.patientId];
    if (data?.adherence && typeof data.adherence.adherence_pct === 'number') {
      totalPct += data.adherence.adherence_pct;
      adherenceCount++;
    }
    if (data?.alerts?.length > 0) {
      data.alerts.forEach(alert => {
        allAlerts.push({
          ...alert,
          patientName: p.name,
          patientId: p.patientId
        });
      });
    }
  });

  const avgAdherence = adherenceCount > 0 ? (totalPct / adherenceCount).toFixed(0) : 0;
  const activeAlerts = allAlerts.filter(a => !a.is_dismissed).sort((a, b) => new Date(b.scheduled_at) - new Date(a.scheduled_at));
  const atRiskCount = new Set(activeAlerts.map(a => a.patientId)).size;

  return (
    <div className="flex flex-col gap-8 py-4">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h2 className="text-3xl font-display font-bold text-foreground tracking-tight">Clinical Overview</h2>
          <p className="text-muted-foreground font-medium">Monitoring {patients.length} active patients under your care.</p>
        </div>
        <div className="flex gap-3">
          <AvailabilityToggle />
          <Button variant="outline" className="h-12 bg-card"><Filter className="w-4 h-4 mr-2" /> All Patients</Button>
          <Button className="h-12 px-6 shadow-lg bg-primary hover:bg-primary/90"><Plus className="w-4 h-4 mr-2" /> Add Patient</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Quick Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <Card className="bg-card">
              <CardContent className="p-6">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Total Patients</p>
                <div className="flex items-center justify-between">
                  <h3 className="text-3xl font-display font-bold">{isLoading ? '…' : patients.length}</h3>
                  <Users className="w-6 h-6 text-primary" />
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card">
              <CardContent className="p-6">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Avg. Adherence</p>
                <div className="flex items-center justify-between">
                  <h3 className="text-3xl font-display font-bold">{avgAdherence}%</h3>
                  <Activity className={`w-6 h-6 ${avgAdherence >= 80 ? 'text-success' : 'text-warning'}`} />
                </div>
              </CardContent>
            </Card>
            <Card className="bg-destructive/5 border-destructive/20">
              <CardContent className="p-6">
                <p className="text-xs font-bold uppercase tracking-widest text-destructive mb-2">High Risk</p>
                <div className="flex items-center justify-between">
                  <h3 className="text-3xl font-display font-bold text-destructive">{atRiskCount}</h3>
                  <AlertCircle className="w-6 h-6 text-destructive" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Patient List */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between border-b-0 pb-2">
              <h3 className="text-xl font-display font-bold">Patient Registry</h3>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  placeholder="Search patients..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-muted/30 border border-border/50 rounded-lg outline-none text-sm font-medium"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-muted/50 text-muted-foreground uppercase text-[10px] font-black tracking-widest">
                    <tr>
                      <th className="px-6 py-4 text-left">Patient Details</th>
                      <th className="px-6 py-4 text-center">Weekly Adherence</th>
                      <th className="px-6 py-4 text-center">Condition Status</th>
                      <th className="px-6 py-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {isLoading && (
                      <tr><td colSpan={4} className="px-6 py-12 text-center text-muted-foreground"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Loading patients…</td></tr>
                    )}
                    {!isLoading && filtered.length === 0 && (
                      <tr><td colSpan={4} className="px-6 py-12 text-center text-muted-foreground">No patients linked to your account yet.</td></tr>
                    )}
                    {filtered.map(p => (
                      <PatientRow 
                        key={p.id} 
                        patient={p} 
                        data={patientsData[p.patientId]} 
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Alerts & Critical Panel */}
        <div className="flex flex-col gap-6">
          <Card className="border-destructive/30 bg-destructive/5 shadow-none">
            <CardHeader>
              <h3 className="text-lg font-display font-bold text-destructive flex items-center gap-2">
                <AlertCircle className="w-5 h-5" /> Adherence Alerts
              </h3>
            </CardHeader>
            <CardContent className="p-6 flex flex-col gap-4">
              {activeAlerts.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No critical alerts at this time.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {activeAlerts.slice(0, 5).map(alert => (
                    <div key={alert.id} className="p-3 bg-white dark:bg-black/20 rounded-lg border border-destructive/10 flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-destructive/10 flex items-center justify-center shrink-0 mt-0.5">
                        <Pill className="w-4 h-4 text-destructive" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-foreground truncate">{alert.patientName}</p>
                        <p className="text-xs text-muted-foreground mt-0.5 leading-snug">
                          Missed <span className="font-semibold text-destructive">{alert.medication_name}</span> scheduled for {new Date(alert.scheduled_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </p>
                      </div>
                    </div>
                  ))}
                  {activeAlerts.length > 5 && (
                    <Button variant="ghost" size="sm" className="w-full text-xs text-destructive hover:text-destructive hover:bg-destructive/10 mt-1">
                      View All {activeAlerts.length} Alerts
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h3 className="text-lg font-display font-bold text-foreground">Recent Consultations</h3>
            </CardHeader>
            <CardContent className="p-6 flex flex-col gap-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="flex items-center gap-4 group cursor-pointer">
                  <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-colors">
                    <UserCircle className="w-6 h-6" />
                  </div>
                  <div className="flex-1">
                    <h5 className="font-bold text-sm text-foreground">Patient Consultation #{1204 + i}</h5>
                    <p className="text-xs text-muted-foreground font-medium">Completed • 2h ago</p>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-muted-foreground" />
                </div>
              ))}
              <Button variant="ghost" className="w-full text-xs font-bold uppercase tracking-widest text-primary mt-2">View History</Button>
            </CardContent>
          </Card>
        </div>
      </div>
      {/* Modals/Dialogs could go here */}
    </div>
  );
}
