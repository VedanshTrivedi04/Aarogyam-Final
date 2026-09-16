import { useSuperAdminInsuranceReports } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { FileText, CheckCircle2, ShieldOff, Clock3 } from 'lucide-react';

export default function SuperAdminInsurance() {
  const { data, isLoading } = useSuperAdminInsuranceReports();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const summary = data?.summary || {};

  const statCards = [
    { title: 'Total Shares', value: summary.total_shares || 0, icon: FileText, color: 'text-blue-600', bgColor: 'bg-blue-50' },
    { title: 'Active', value: summary.active || 0, icon: CheckCircle2, color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
    { title: 'Revoked', value: summary.revoked || 0, icon: ShieldOff, color: 'text-red-600', bgColor: 'bg-red-50' },
    { title: 'Expired', value: summary.expired || 0, icon: Clock3, color: 'text-slate-600', bgColor: 'bg-slate-100' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <FileText className="w-6 h-6 mr-2 text-accent-500" />
          Insurance & Report Sharing
        </h1>
        <p className="text-slate-500 mt-1">Adherence reports shared with insurers, employers, and doctors.</p>
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
            <h2 className="text-lg font-bold text-slate-800">Report Shares</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
                <tr>
                  <th className="py-3 px-4">Patient</th>
                  <th className="py-3 px-4">Recipient</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Expires</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.shares?.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900">{s.patient}</td>
                    <td className="py-3 px-4">{s.recipient_name}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                        {s.recipient_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">{new Date(s.expires_at).toLocaleDateString()}</td>
                    <td className="py-3 px-4">
                      {s.is_revoked ? (
                        <span className="text-red-600 font-medium">Revoked</span>
                      ) : (
                        <span className="text-emerald-600 font-medium">Active</span>
                      )}
                    </td>
                  </tr>
                ))}
                {(!data?.shares || data.shares.length === 0) && (
                  <tr>
                    <td colSpan="5" className="py-8 text-center text-slate-500">No report shares yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4">Recent Access</h2>
            <div className="space-y-3">
              {data?.recent_access?.map((a) => (
                <div key={a.id} className="text-sm border-b border-slate-50 pb-2">
                  <p className="font-medium text-slate-900">{a.recipient_name}</p>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{a.accessor_ip}</span>
                    <span>{new Date(a.accessed_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
              {(!data?.recent_access || data.recent_access.length === 0) && (
                <p className="text-center text-slate-400 py-6">No access recorded yet.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
