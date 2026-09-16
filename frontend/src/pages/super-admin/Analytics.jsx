import { useSuperAdminAnalytics } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { BarChart3, TrendingUp, IndianRupee, Building2, Cpu, Award, FlaskConical } from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';

const TEAL = '#14b8a6';
const VIOLET = '#8b5cf6';
const ERROR = '#ef4444';
const BLUE = '#3b82f6';

const AXIS_STYLE = { fontSize: 12, fill: '#94a3b8' };

function formatShortDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatMonth(value) {
  if (!value) return '';
  return new Date(value).toLocaleDateString(undefined, { month: 'short', year: '2-digit' });
}

function ChartCard({ title, icon: Icon, iconColor, children }) {
  return (
    <Card className="border-slate-200/60 shadow-sm">
      <CardContent className="p-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
          <Icon className={`w-5 h-5 mr-2 ${iconColor}`} />
          {title}
        </h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            {children}
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SuperAdminAnalytics() {
  const { data, isLoading } = useSuperAdminAnalytics();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const snapshot = data?.snapshot || {};

  const snapshotCards = [
    { title: 'Device Fleet Health', value: `${snapshot.device_fleet_health_pct || 0}%`, icon: Cpu, color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
    { title: 'Badges Earned', value: snapshot.total_badges_earned || 0, icon: Award, color: 'text-accent-600', bgColor: 'bg-accent-500/10' },
    { title: 'Total Tenants', value: snapshot.total_tenants || 0, icon: Building2, color: 'text-blue-600', bgColor: 'bg-blue-50' },
    { title: 'Open Safety Reports', value: snapshot.open_safety_reports || 0, icon: FlaskConical, color: 'text-red-600', bgColor: 'bg-red-50' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <BarChart3 className="w-6 h-6 mr-2 text-accent-500" />
          Unified Analytics
        </h1>
        <p className="text-slate-500 mt-1">Cross-cutting trends pulled from every portal into one view.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {snapshotCards.map((stat, idx) => (
          <Card key={idx} className="border-slate-200/60 shadow-sm">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">{stat.title}</p>
                  <h3 className="text-3xl font-bold text-slate-900">{stat.value}</h3>
                </div>
                <div className={`p-3 rounded-xl ${stat.bgColor}`}>
                  <stat.icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Adherence Trend (14d)" icon={TrendingUp} iconColor="text-primary">
          <AreaChart data={data?.adherence_trend || []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="adherenceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={TEAL} stopOpacity={0.25} />
                <stop offset="95%" stopColor={TEAL} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="date" tickFormatter={formatShortDate} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={AXIS_STYLE} axisLine={false} tickLine={false} width={36} />
            <Tooltip
              labelFormatter={formatShortDate}
              formatter={(value) => [`${value}%`, 'Adherence']}
              contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e2e8f0' }}
            />
            <Area type="monotone" dataKey="avg_pct" stroke={TEAL} strokeWidth={2} fill="url(#adherenceFill)" />
          </AreaChart>
        </ChartCard>

        <ChartCard title="Alert Volume (14d)" icon={BarChart3} iconColor="text-red-500">
          <BarChart data={data?.alert_volume_trend || []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="date" tickFormatter={formatShortDate} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={AXIS_STYLE} axisLine={false} tickLine={false} width={30} />
            <Tooltip
              labelFormatter={formatShortDate}
              formatter={(value) => [value, 'Missed Doses']}
              contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e2e8f0' }}
            />
            <Bar dataKey="count" fill={ERROR} radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Revenue Trend (6mo)" icon={IndianRupee} iconColor="text-accent-500">
          <AreaChart data={data?.revenue_trend || []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={VIOLET} stopOpacity={0.25} />
                <stop offset="95%" stopColor={VIOLET} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="month" tickFormatter={formatMonth} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
            <YAxis tick={AXIS_STYLE} axisLine={false} tickLine={false} width={44} />
            <Tooltip
              labelFormatter={formatMonth}
              formatter={(value) => [`₹${value}`, 'Revenue']}
              contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e2e8f0' }}
            />
            <Area type="monotone" dataKey="total" stroke={VIOLET} strokeWidth={2} fill="url(#revenueFill)" />
          </AreaChart>
        </ChartCard>

        <ChartCard title="Tenant Growth (6mo)" icon={Building2} iconColor="text-blue-500">
          <BarChart data={data?.tenant_growth || []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="month" tickFormatter={formatMonth} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={AXIS_STYLE} axisLine={false} tickLine={false} width={30} />
            <Tooltip
              labelFormatter={formatMonth}
              formatter={(value) => [value, 'New Tenants']}
              contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e2e8f0' }}
            />
            <Bar dataKey="count" fill={BLUE} radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ChartCard>
      </div>
    </div>
  );
}
