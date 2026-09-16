import { Link } from 'react-router-dom';
import { useSuperAdminOverview, useSuperAdminPortals } from '@/hooks/useSuperAdmin';
import { Users, Bell, TrendingUp, UserPlus, Stethoscope, HeartHandshake, User, Pill } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';

const PORTAL_ICONS = {
  PATIENT: User,
  CAREGIVER: HeartHandshake,
  DOCTOR: Stethoscope,
  PHARMACY: Pill,
};

const PORTAL_COLORS = {
  PATIENT: { color: 'text-blue-600', bgColor: 'bg-blue-50' },
  CAREGIVER: { color: 'text-violet-600', bgColor: 'bg-violet-50' },
  DOCTOR: { color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
  PHARMACY: { color: 'text-orange-600', bgColor: 'bg-orange-50' },
};

export default function SuperAdminDashboard() {
  const { data: overview, isLoading: isOverviewLoading } = useSuperAdminOverview();
  const { data: portals, isLoading: isPortalsLoading } = useSuperAdminPortals();

  if (isOverviewLoading || isPortalsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const adherence = overview?.global_adherence_pct || 0;

  const statCards = [
    {
      title: 'Total Active Users',
      value: overview?.total_active_users || 0,
      icon: Users,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      trend: `+${overview?.new_users_today || 0} today`,
    },
    {
      title: 'Total Open Alerts',
      value: overview?.total_open_alerts || 0,
      icon: Bell,
      color: overview?.total_open_alerts > 0 ? 'text-red-600' : 'text-emerald-600',
      bgColor: overview?.total_open_alerts > 0 ? 'bg-red-50' : 'bg-emerald-50',
      trend: 'Across all portals',
    },
    {
      title: 'Global Adherence',
      value: `${adherence}%`,
      icon: TrendingUp,
      color: adherence >= 80 ? 'text-green-600' : 'text-orange-600',
      bgColor: adherence >= 80 ? 'bg-green-50' : 'bg-orange-50',
      trend: '7-Day Average',
    },
    {
      title: 'New Signups',
      value: overview?.new_users_today || 0,
      icon: UserPlus,
      color: 'text-accent-600',
      bgColor: 'bg-accent-500/10',
      trend: 'Today',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Cross-Portal Overview</h1>
        <p className="text-slate-500 mt-1">Business & health metrics across every stakeholder portal.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, idx) => (
          <Card key={idx} className="border-slate-200/60 shadow-sm hover:shadow-md transition-shadow">
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
              <div className="mt-4 flex items-center text-sm font-medium text-slate-600">
                <span>{stat.trend}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div>
        <h2 className="text-lg font-bold text-slate-800 mb-4">Portals at a Glance</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {portals?.map((portal) => {
            const Icon = PORTAL_ICONS[portal.portal] || Users;
            const palette = PORTAL_COLORS[portal.portal] || { color: 'text-slate-600', bgColor: 'bg-slate-50' };
            return (
              <Link key={portal.portal} to={`/super-admin/portals/${portal.portal.toLowerCase()}`}>
              <Card className="border-slate-200/60 shadow-sm hover:shadow-md transition-shadow cursor-pointer h-full">
                <CardContent className="p-6">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className={`p-2.5 rounded-xl ${palette.bgColor}`}>
                      <Icon className={`w-5 h-5 ${palette.color}`} />
                    </div>
                    <h3 className="font-bold text-slate-900">{portal.label}</h3>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Active Users</span>
                      <span className="font-semibold text-slate-900">{portal.active_users}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Pending Tasks</span>
                      <span className="font-semibold text-slate-900">{portal.pending_tasks}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Alerts</span>
                      <span className={`font-semibold ${portal.alerts > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                        {portal.alerts}
                      </span>
                    </div>
                    {portal.adherence_pct !== null && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">Adherence</span>
                        <span className="font-semibold text-slate-900">{portal.adherence_pct}%</span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
