import { useSuperAdminDeviceFleet } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { Cpu, Wifi, WifiOff, BatteryLow, AlertTriangle } from 'lucide-react';

export default function SuperAdminDevices() {
  const { data, isLoading } = useSuperAdminDeviceFleet();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const summary = data?.summary || {};

  const statCards = [
    { title: 'Online', value: summary.online || 0, icon: Wifi, color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
    { title: 'Offline', value: summary.offline || 0, icon: WifiOff, color: 'text-slate-600', bgColor: 'bg-slate-100' },
    { title: 'Low Battery', value: summary.low_battery || 0, icon: BatteryLow, color: 'text-orange-600', bgColor: 'bg-orange-50' },
    { title: 'Faulty', value: summary.faulty || 0, icon: AlertTriangle, color: 'text-red-600', bgColor: 'bg-red-50' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <Cpu className="w-6 h-6 mr-2 text-accent-500" />
          Device Fleet
        </h1>
        <p className="text-slate-500 mt-1">Fleet-wide health for every IoT pill dispenser on the platform.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="border-slate-200/60 shadow-sm overflow-hidden lg:col-span-2">
          <div className="p-4 border-b border-slate-100">
            <h2 className="text-lg font-bold text-slate-800">Devices</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
                <tr>
                  <th className="py-3 px-4">Device</th>
                  <th className="py-3 px-4">Owner</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Battery</th>
                  <th className="py-3 px-4">Firmware</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.devices?.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900">{d.device_name}</td>
                    <td className="py-3 px-4 text-slate-500">{d.owner_email}</td>
                    <td className="py-3 px-4">
                      {d.is_online ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-emerald-100 text-emerald-700">
                          <Wifi className="w-3 h-3 mr-1" /> Online
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-600">
                          <WifiOff className="w-3 h-3 mr-1" /> Offline
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {d.battery_level != null ? `${d.battery_level}%` : '—'}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{d.firmware_version || '—'}</td>
                  </tr>
                ))}
                {(!data?.devices || data.devices.length === 0) && (
                  <tr>
                    <td colSpan="5" className="py-8 text-center text-slate-500">No devices registered.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
              <AlertTriangle className="w-5 h-5 mr-2 text-orange-500" />
              Recent Fault Events
            </h2>
            <div className="space-y-3">
              {data?.recent_faults?.map((f) => (
                <div key={f.id} className="text-sm border-b border-slate-50 pb-2">
                  <p className="font-medium text-slate-900">{f.device_name}</p>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{f.event_type.replace(/_/g, ' ')}</span>
                    <span>{new Date(f.occurred_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
              {(!data?.recent_faults || data.recent_faults.length === 0) && (
                <p className="text-center text-slate-400 py-6">No recent fault events.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
