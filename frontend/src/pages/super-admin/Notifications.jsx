import { useSuperAdminNotificationsCenter } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { MessageSquare, Send, CheckCircle2, XCircle } from 'lucide-react';

export default function SuperAdminNotifications() {
  const { data, isLoading } = useSuperAdminNotificationsCenter();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const overall = data?.overall || {};
  const telegram = data?.telegram || {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <MessageSquare className="w-6 h-6 mr-2 text-accent-500" />
          Notifications Center
        </h1>
        <p className="text-slate-500 mt-1">Cross-channel delivery health across push, email, SMS, and Telegram.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
              <Send className="w-5 h-5 mr-2 text-accent-500" />
              Overall Delivery
            </h2>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm font-medium mb-1">
                  <span className="text-slate-600">Success Rate</span>
                  <span className="text-slate-900">{overall.rate_pct || 0}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${overall.rate_pct >= 95 ? 'bg-emerald-500' : 'bg-orange-500'}`}
                    style={{ width: `${overall.rate_pct || 0}%` }}
                  ></div>
                </div>
              </div>
              <div className="flex justify-between text-sm">
                <div className="text-center">
                  <p className="text-slate-500 mb-1">Total</p>
                  <p className="font-bold text-lg text-slate-900">{overall.total || 0}</p>
                </div>
                <div className="text-center">
                  <p className="text-slate-500 mb-1">Delivered</p>
                  <p className="font-bold text-lg text-emerald-600">{overall.delivered || 0}</p>
                </div>
                <div className="text-center">
                  <p className="text-slate-500 mb-1">Failed</p>
                  <p className="font-bold text-lg text-red-600">{overall.failed || 0}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4">Telegram Bot</h2>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-slate-900">{telegram.total_sessions || 0}</p>
                <p className="text-xs text-slate-500 mt-1">Total Sessions</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-600">{telegram.onboarded || 0}</p>
                <p className="text-xs text-slate-500 mt-1">Onboarded</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-accent-600">{telegram.active_24h ?? '—'}</p>
                <p className="text-xs text-slate-500 mt-1">Active (24h)</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200/60 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-800">Delivery by Channel</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
              <tr>
                <th className="py-3 px-6">Channel</th>
                <th className="py-3 px-6">Total</th>
                <th className="py-3 px-6">Delivered</th>
                <th className="py-3 px-6">Failed</th>
                <th className="py-3 px-6">Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.by_channel?.map((row) => (
                <tr key={row.channel} className="hover:bg-slate-50/50 transition-colors">
                  <td className="py-3 px-6 font-medium text-slate-900">{row.channel}</td>
                  <td className="py-3 px-6">{row.total}</td>
                  <td className="py-3 px-6 text-emerald-600">
                    <span className="inline-flex items-center"><CheckCircle2 className="w-3 h-3 mr-1" />{row.delivered}</span>
                  </td>
                  <td className="py-3 px-6 text-red-600">
                    <span className="inline-flex items-center"><XCircle className="w-3 h-3 mr-1" />{row.failed}</span>
                  </td>
                  <td className="py-3 px-6 font-medium">{row.rate_pct}%</td>
                </tr>
              ))}
              {(!data?.by_channel || data.by_channel.length === 0) && (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-slate-500">No notification data.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
