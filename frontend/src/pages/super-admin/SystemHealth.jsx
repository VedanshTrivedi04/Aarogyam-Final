import { useSuperAdminSystemHealth } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { Activity, CheckCircle2, AlertTriangle, Clock, Cpu, MessageSquareWarning } from 'lucide-react';

export default function SuperAdminSystemHealth() {
  const { data, isLoading } = useSuperAdminSystemHealth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const celery = data?.celery || {};
  const notifications = data?.notifications || {};
  const connectivity = data?.device_connectivity || {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <Activity className="w-6 h-6 mr-2 text-accent-500" />
          System Health
        </h1>
        <p className="text-slate-500 mt-1">Background jobs, notification pipeline, and device connectivity.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-slate-500">Celery Jobs</p>
              <Cpu className="w-5 h-5 text-blue-500" />
            </div>
            <h3 className="text-3xl font-bold text-slate-900">{celery.enabled_jobs || 0}/{celery.total_jobs || 0}</h3>
            <p className="text-xs text-slate-500 mt-1">Enabled / Total</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-slate-500">Notification Error Rate</p>
              <MessageSquareWarning className={`w-5 h-5 ${notifications.error_rate_pct > 5 ? 'text-red-500' : 'text-emerald-500'}`} />
            </div>
            <h3 className="text-3xl font-bold text-slate-900">{notifications.error_rate_pct || 0}%</h3>
            <p className="text-xs text-slate-500 mt-1">{notifications.failed || 0} failed of {notifications.total || 0}</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-slate-500">Device Connectivity</p>
              <Activity className="w-5 h-5 text-emerald-500" />
            </div>
            <h3 className="text-3xl font-bold text-slate-900">{connectivity.online_pct || 0}%</h3>
            <p className="text-xs text-slate-500 mt-1">{connectivity.online || 0} online of {connectivity.total || 0}</p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200/60 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-800">Background Tasks (Celery Beat)</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
              <tr>
                <th className="py-3 px-6">Task Name</th>
                <th className="py-3 px-6">Status</th>
                <th className="py-3 px-6">Last Run At</th>
                <th className="py-3 px-6 text-right">Run Count</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {celery.jobs?.map((job, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                  <td className="py-3 px-6 font-medium text-slate-900">{job.name}</td>
                  <td className="py-3 px-6">
                    {job.enabled ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-700">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> Enabled
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                        <AlertTriangle className="w-3 h-3 mr-1" /> Disabled
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-6 text-slate-500">
                    {job.last_run_at ? (
                      <div className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(job.last_run_at).toLocaleString()}</span>
                      </div>
                    ) : (
                      'Never'
                    )}
                  </td>
                  <td className="py-3 px-6 text-right font-medium">{job.total_run_count}</td>
                </tr>
              ))}
              {(!celery.jobs || celery.jobs.length === 0) && (
                <tr>
                  <td colSpan="4" className="py-8 text-center text-slate-500">No background tasks registered.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
