import { useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Download, Calendar as CalendarIcon, ChevronRight, TrendingUp, Loader2, AlertCircle, X } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useAdherenceSummary, useAdherenceTimeline, useMedicationBreakdown, useExportAdherenceReport } from '@/hooks/usePatientReports';

const rangeOptions = [
  { label: '7D', value: 7 },
  { label: '30D', value: 30 },
  { label: '90D', value: 90 },
];

function formatDateLabel(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function statusClass(rate) {
  if (rate >= 85) return 'bg-success/20 border-success/30 text-success';
  if (rate >= 60) return 'bg-accent/20 border-accent/30 text-accent';
  return 'bg-destructive/20 border-destructive/30 text-destructive';
}

export default function Reports({ patientId = null }) {
  const [days, setDays] = useState(30);
  const [isExporting, setIsExporting] = useState(false);
  const [selectedDayEntry, setSelectedDayEntry] = useState(null);

  const summaryQuery = useAdherenceSummary(days, patientId);
  const timelineQuery = useAdherenceTimeline(days, patientId);
  const medicationQuery = useMedicationBreakdown(days, patientId);
  const exportReport = useExportAdherenceReport(patientId);

  const summary = summaryQuery.data || {};
  const timeline = timelineQuery.data || [];
  const breakdown = medicationQuery.data || [];

  const chartData = useMemo(() => {
    return [...timeline]
      .slice(-Math.min(timeline.length, 14))
      .map((item) => ({
        day: formatDateLabel(item.date),
        taken: item.taken ?? 0,
        missed: item.missed ?? 0,
        skipped: item.skipped ?? 0,
      }));
  }, [timeline]);

  const heatmapCells = useMemo(() => {
    const map = new Map(timeline.map((entry) => [entry.date, entry]));
    
    const today = new Date();
    const currentDayOfWeek = today.getDay(); 
    const daysToSunday = currentDayOfWeek === 0 ? 0 : 7 - currentDayOfWeek;
    
    const endDate = new Date(today);
    endDate.setDate(endDate.getDate() + daysToSunday);

    return Array.from({ length: 35 }, (_, index) => {
      const d = new Date(endDate);
      d.setDate(d.getDate() - (34 - index));
      
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      
      if (d > today) {
        return { key, label: d.getDate(), state: 'none', rate: 0, entry: null };
      }

      const entry = map.get(key);
      const safeEntry = entry || { date: key, taken: 0, missed: 0, skipped: 0, total: 0, adherence_pct: 0 };
      
      const rate = safeEntry.adherence_pct ?? 0;
      const state = safeEntry.total === 0 ? 'none' : rate >= 85 ? 'taken' : rate >= 60 ? 'warning' : 'missed';
      
      return { key, label: d.getDate(), state, rate, entry: safeEntry };
    });
  }, [timeline]);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await exportReport({ days, format: 'pdf' });
      // res is the full axios response; res.data is already the Blob
      const contentType = res.headers?.['content-type'] || 'application/pdf';
      const blob = new Blob([res.data], { type: contentType });
      const objectUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `adherence_report_${days}d.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (error) {
      // useExportAdherenceReport now correctly parses blob errors and throws
      // a plain Error with a human-readable message.
      alert(error?.message || 'Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const isLoading = summaryQuery.isLoading || timelineQuery.isLoading || medicationQuery.isLoading;

  return (
    <div className="flex flex-col gap-8 py-4 font-sans">
      <div className="flex justify-end items-center gap-3">
        <div className="flex bg-muted p-1 rounded-xl">
          {rangeOptions.map((item) => (
            <button
              key={item.value}
              onClick={() => setDays(item.value)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${days === item.value ? 'bg-card shadow-sm text-primary' : 'text-muted-foreground hover:text-foreground'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <Button className="h-12 px-6 rounded-xl shadow-lg bg-accent hover:bg-accent/90" onClick={handleExport} disabled={isExporting || isLoading}>
          {isExporting ? <Loader2 className="w-5 h-5 mr-2 animate-spin" /> : <Download className="w-5 h-5 mr-2" />}
          Export PDF Report
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-primary text-white border-none shadow-elevation-2">
          <CardContent className="p-6">
            <p className="text-xs font-bold uppercase tracking-widest opacity-70 mb-2">Overall Score</p>
            <div className="flex items-end gap-3">
              <h3 className="text-4xl font-display font-bold">{summary.adherence_pct ?? 0}%</h3>
              <Badge variant="success" className="mb-1 bg-white/20 text-white border-none">{summary.days ?? days} days</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Total Doses</p>
            <div className="flex items-end gap-3">
              <h3 className="text-4xl font-display font-bold text-foreground">{summary.total_scheduled ?? 0}</h3>
              <p className="text-sm text-muted-foreground font-medium mb-1">Scheduled</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Missed Doses</p>
            <div className="flex items-end gap-3">
              <h3 className="text-4xl font-display font-bold text-destructive">{summary.missed ?? 0}</h3>
              <p className="text-sm text-muted-foreground font-medium mb-1">Needs attention</p>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-secondary/30 border-primary/20">
          <CardContent className="p-6">
            <p className="text-xs font-bold uppercase tracking-widest text-primary mb-2">Current Streak</p>
            <div className="flex items-end gap-3">
              <h3 className="text-4xl font-display font-bold text-primary">{summary.taken ?? 0}</h3>
              <p className="text-sm text-primary/70 font-medium mb-1">Taken</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <h3 className="text-xl font-display font-bold flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" /> Recent Performance
            </h3>
            <Badge variant="primary">Backend data</Badge>
          </CardHeader>
          <CardContent className="p-6 h-80">
            {isLoading ? (
              <div className="h-full flex items-center justify-center text-muted-foreground gap-3">
                <Loader2 className="w-5 h-5 animate-spin" /> Loading chart...
              </div>
            ) : chartData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#7A8A99', fontSize: 12, fontWeight: 600 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#7A8A99', fontSize: 12, fontWeight: 600 }} allowDecimals={false} />
                  <Tooltip cursor={{ fill: '#F1F5F9' }} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }} />
                  <Bar dataKey="taken" fill="#0B6E7A" radius={[4, 4, 0, 0]} barSize={28} />
                  <Bar dataKey="missed" fill="#FF6B6B" radius={[4, 4, 0, 0]} barSize={28} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground gap-2">
                <AlertCircle className="w-5 h-5" /> No adherence history found.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-xl font-display font-bold flex items-center gap-2">
              <CalendarIcon className="w-5 h-5 text-primary" /> Heatmap
            </h3>
          </CardHeader>
          <CardContent className="p-6">
            <div className="grid grid-cols-7 gap-2">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
                <div key={d} className="text-center text-[10px] font-black text-muted-foreground mb-2">{d[0]}</div>
              ))}
              {heatmapCells.map((cell) => (
                <div
                  key={cell.key}
                  onClick={() => cell.entry && setSelectedDayEntry(cell.entry)}
                  className={`aspect-square rounded-md border flex items-center justify-center text-[10px] font-bold cursor-pointer transition-transform hover:scale-110 hover:shadow-md ${cell.state === 'taken' ? 'bg-success/20 border-success/30 text-success' : cell.state === 'warning' ? 'bg-accent/20 border-accent/30 text-accent' : cell.state === 'missed' ? 'bg-destructive/20 border-destructive/30 text-destructive' : 'bg-muted border-border text-muted-foreground'}`}
                  title={`${cell.key}: ${cell.rate}%`}
                >
                  {cell.label}
                </div>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap justify-center gap-4 text-xs font-bold uppercase tracking-wider">
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-success/20 border border-success/30" /> Taken</div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-accent/20 border border-accent/30" /> Partial</div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-destructive/20 border border-destructive/30" /> Missed</div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-muted border border-border" /> No Dose</div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <h3 className="text-xl font-display font-bold">Medicine Breakdown</h3>
          <Button variant="ghost" size="sm" className="font-bold text-primary">Live breakdown <ChevronRight className="ml-1 w-4 h-4" /></Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50 text-muted-foreground uppercase text-[10px] font-black tracking-widest">
                <tr>
                  <th className="px-6 py-4 text-left">Medicine Name</th>
                  <th className="px-6 py-4 text-center">Adherence Rate</th>
                  <th className="px-6 py-4 text-center">Status</th>
                  <th className="px-6 py-4 text-right">Last 7 Days</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {breakdown.length ? breakdown.map((med) => (
                  <tr key={med.prescription_id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-5 font-bold text-foreground">{med.medication}</td>
                    <td className="px-6 py-5">
                      <div className="flex items-center justify-center gap-3">
                        <div className="flex-1 max-w-[100px] h-2 bg-secondary rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${med.adherence_pct > 85 ? 'bg-success' : med.adherence_pct > 60 ? 'bg-accent' : 'bg-destructive'}`} style={{ width: `${med.adherence_pct}%` }} />
                        </div>
                        <span className="text-sm font-black text-foreground">{med.adherence_pct}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-5 text-center">
                      <Badge variant={med.adherence_pct > 85 ? 'success' : med.adherence_pct > 60 ? 'warning' : 'danger'} className="uppercase">
                        {med.adherence_pct > 85 ? 'excellent' : med.adherence_pct > 60 ? 'good' : 'watch'}
                      </Badge>
                    </td>
                    <td className="px-6 py-5 text-right text-sm text-muted-foreground font-semibold">{med.total} doses</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="4" className="px-6 py-10 text-center text-muted-foreground">No medicine breakdown available yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {selectedDayEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <Card className="w-full max-w-md shadow-2xl border-none relative overflow-visible">
            <Button
              variant="secondary"
              size="icon"
              className="absolute -top-3 -right-3 rounded-full shadow-lg border bg-background hover:bg-muted z-10"
              onClick={() => setSelectedDayEntry(null)}
            >
              <X className="w-4 h-4" />
            </Button>
            <CardHeader className="bg-primary/5 rounded-t-xl border-b border-border/50 pb-4">
              <h3 className="text-xl font-display font-bold text-center">
                Analytics for {formatDateLabel(selectedDayEntry.date)}
              </h3>
              <p className="text-center text-sm font-semibold text-muted-foreground">
                Daily Adherence Score: <span className={statusClass(selectedDayEntry.adherence_pct)}>{selectedDayEntry.adherence_pct ?? 0}%</span>
              </p>
            </CardHeader>
            <CardContent className="pt-6">
              {(selectedDayEntry.total || 0) > 0 ? (
                <>
                  <div className="h-56 relative flex items-center justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={[
                            { name: 'Taken', value: selectedDayEntry.taken || 0, color: '#0B6E7A' },
                            { name: 'Missed', value: selectedDayEntry.missed || 0, color: '#FF6B6B' },
                            { name: 'Skipped', value: selectedDayEntry.skipped || 0, color: '#94A3B8' },
                          ].filter(d => d.value > 0)}
                          cx="50%"
                          cy="50%"
                          innerRadius={68}
                          outerRadius={90}
                          paddingAngle={6}
                          dataKey="value"
                        >
                          {
                            [
                              { name: 'Taken', value: selectedDayEntry.taken || 0, color: '#0B6E7A' },
                              { name: 'Missed', value: selectedDayEntry.missed || 0, color: '#FF6B6B' },
                              { name: 'Skipped', value: selectedDayEntry.skipped || 0, color: '#94A3B8' },
                            ].filter(d => d.value > 0).map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                            ))
                          }
                        </Pie>
                        <Tooltip 
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                          itemStyle={{ fontWeight: 600 }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none drop-shadow-sm">
                      <span className="text-5xl font-display font-black text-foreground tracking-tight">{selectedDayEntry.total || 0}</span>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mt-1">Total Doses</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    <div className="flex flex-col items-center p-3 bg-success/10 rounded-xl">
                       <div className="text-2xl font-black text-success">{selectedDayEntry.taken || 0}</div>
                       <div className="text-[10px] font-bold text-success/70 uppercase tracking-wider mt-1">Taken</div>
                    </div>
                    <div className="flex flex-col items-center p-3 bg-destructive/10 rounded-xl">
                       <div className="text-2xl font-black text-destructive">{selectedDayEntry.missed || 0}</div>
                       <div className="text-[10px] font-bold text-destructive/70 uppercase tracking-wider mt-1">Missed</div>
                    </div>
                    <div className="flex flex-col items-center p-3 bg-muted rounded-xl">
                       <div className="text-2xl font-black text-muted-foreground">{selectedDayEntry.skipped || 0}</div>
                       <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mt-1">Skipped</div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
                  <AlertCircle className="w-12 h-12 mb-3 opacity-20" />
                  <p className="font-semibold">No scheduled doses for this day.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
