import { useSuperAdminGeofencing } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { MapPin, PhoneCall, BellRing, AlertTriangle } from 'lucide-react';

export default function SuperAdminGeofencing() {
  const { data, isLoading } = useSuperAdminGeofencing();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const summary = data?.summary || {};

  const statCards = [
    { title: 'Active Zones', value: summary.active_zones || 0, icon: MapPin, color: 'text-blue-600', bgColor: 'bg-blue-50' },
    { title: 'Total Zones', value: summary.total_zones || 0, icon: MapPin, color: 'text-slate-600', bgColor: 'bg-slate-100' },
    { title: 'Exits w/ Pending Dose', value: summary.exits_with_pending_dose || 0, icon: AlertTriangle, color: 'text-red-600', bgColor: 'bg-red-50' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <MapPin className="w-6 h-6 mr-2 text-accent-500" />
          Geofencing Overview
        </h1>
        <p className="text-slate-500 mt-1">Cross-patient zone-exit events, not scoped to a single caregiver.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {statCards.map((stat, idx) => (
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

      <Card className="border-slate-200/60 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-800">Recent Zone Exits</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
              <tr>
                <th className="py-3 px-4">Patient</th>
                <th className="py-3 px-4">Zone</th>
                <th className="py-3 px-4">Triggered At</th>
                <th className="py-3 px-4">Pending Meds</th>
                <th className="py-3 px-4">Response</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.recent_exits?.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="py-3 px-4 font-medium text-slate-900">{e.patient}</td>
                  <td className="py-3 px-4">{e.zone_label}</td>
                  <td className="py-3 px-4 text-slate-500">{new Date(e.triggered_at).toLocaleString()}</td>
                  <td className="py-3 px-4">
                    {e.pending_meds_count > 0 ? (
                      <span className="text-red-600 font-medium">{e.pending_meds_count} pending</span>
                    ) : (
                      <span className="text-slate-400">None</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2 text-xs">
                      {e.alert_sent && (
                        <span className="inline-flex items-center px-2 py-1 rounded-md bg-blue-100 text-blue-700">
                          <BellRing className="w-3 h-3 mr-1" /> Alerted
                        </span>
                      )}
                      {e.call_placed && (
                        <span className="inline-flex items-center px-2 py-1 rounded-md bg-emerald-100 text-emerald-700">
                          <PhoneCall className="w-3 h-3 mr-1" /> Called
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {(!data?.recent_exits || data.recent_exits.length === 0) && (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-slate-500">No zone exits recorded.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
