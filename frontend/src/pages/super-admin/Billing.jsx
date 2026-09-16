import {
  useSuperAdminBilling,
  useSuperAdminCaregiverSubscriptions,
  useSuperAdminAssignCaregiverSubscription,
  useSuperAdminExtendCaregiverSubscription,
  useSuperAdminCancelCaregiverSubscription,
} from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { CreditCard, IndianRupee, TrendingDown, Receipt, Clock, HeartHandshake, CalendarClock, Ban, ShieldCheck } from 'lucide-react';

function CaregiverSubscriptions() {
  const { data, isLoading } = useSuperAdminCaregiverSubscriptions();
  const assignPlan = useSuperAdminAssignCaregiverSubscription();
  const extendSub = useSuperAdminExtendCaregiverSubscription();
  const cancelSub = useSuperAdminCancelCaregiverSubscription();

  const plans = data?.plans || [];
  const caregivers = data?.caregivers || [];

  const handleAssign = async (userId, planSlug) => {
    if (!planSlug) return;
    await assignPlan.mutateAsync({ userId, plan_slug: planSlug, days: 30 });
  };

  const handleExtend = async (userId) => {
    const daysStr = window.prompt('Extend by how many days?', '30');
    if (!daysStr) return;
    const days = parseInt(daysStr, 10);
    if (!isNaN(days) && days > 0) {
      await extendSub.mutateAsync({ userId, days });
    }
  };

  const handleCancel = async (userId) => {
    if (window.confirm('Cancel this caregiver\'s subscription?')) {
      await cancelSub.mutateAsync({ userId });
    }
  };

  return (
    <Card className="border-slate-200/60 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-800 flex items-center">
          <HeartHandshake className="w-5 h-5 mr-2 text-accent-500" />
          Caregiver Subscriptions
        </h2>
        <p className="text-sm text-slate-500 mt-1">Assign plans, extend, or cancel subscriptions for caregiver accounts.</p>
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
              <tr>
                <th className="py-3 px-4">Caregiver</th>
                <th className="py-3 px-4">Plan</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Expires At</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {caregivers.map((cg) => (
                <tr key={cg.user_id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="py-3 px-4">
                    <div className="font-medium text-slate-900">{cg.full_name}</div>
                    <div className="text-xs text-slate-500">{cg.email}</div>
                  </td>
                  <td className="py-3 px-4">
                    <select
                      value={cg.subscription?.plan_slug || ''}
                      onChange={(e) => handleAssign(cg.user_id, e.target.value)}
                      disabled={assignPlan.isPending}
                      className="text-xs font-medium bg-slate-100 text-slate-700 rounded-md px-2 py-1 border-0 focus:ring-accent-500"
                    >
                      <option value="" disabled>No plan</option>
                      {plans.map((p) => (
                        <option key={p.slug} value={p.slug}>{p.name}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-3 px-4">
                    {cg.subscription?.status === 'ACTIVE' ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-700">
                        <ShieldCheck className="w-3 h-3 mr-1" /> Active
                      </span>
                    ) : cg.subscription ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                        {cg.subscription.status}
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-slate-500">
                    {cg.subscription?.expires_at ? new Date(cg.subscription.expires_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="py-3 px-4 text-right space-x-2 whitespace-nowrap">
                    <Button
                      variant="outline" size="sm" className="h-7 text-xs"
                      onClick={() => handleExtend(cg.user_id)}
                      disabled={!cg.subscription || extendSub.isPending}
                    >
                      <CalendarClock className="w-3 h-3 mr-1" /> Extend
                    </Button>
                    <Button
                      size="sm"
                      className="h-7 text-xs border-0 bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700"
                      onClick={() => handleCancel(cg.user_id)}
                      disabled={!cg.subscription || cg.subscription.status === 'CANCELED' || cancelSub.isPending}
                    >
                      <Ban className="w-3 h-3 mr-1" /> Cancel
                    </Button>
                  </td>
                </tr>
              ))}
              {caregivers.length === 0 && (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-slate-500">No caregivers found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function SuperAdminBilling() {
  const { data, isLoading } = useSuperAdminBilling();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Active Subscriptions',
      value: data?.status_counts?.active || 0,
      icon: CreditCard,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Revenue (30d)',
      value: `₹${data?.revenue_30d || 0}`,
      icon: IndianRupee,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50',
    },
    {
      title: 'Churn Rate',
      value: `${data?.churn_rate_pct || 0}%`,
      icon: TrendingDown,
      color: data?.churn_rate_pct > 10 ? 'text-red-600' : 'text-orange-600',
      bgColor: data?.churn_rate_pct > 10 ? 'bg-red-50' : 'bg-orange-50',
    },
    {
      title: 'Paid Invoices (30d)',
      value: data?.paid_invoices_30d || 0,
      icon: Receipt,
      color: 'text-accent-600',
      bgColor: 'bg-accent-500/10',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Subscriptions & Billing</h1>
        <p className="text-slate-500 mt-1">Revenue, churn, and plan distribution across the platform.</p>
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
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4">Subscriptions by Plan & Status</h2>
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="text-slate-500 border-b border-slate-100">
                <tr>
                  <th className="py-2">Plan</th>
                  <th className="py-2">Status</th>
                  <th className="py-2 text-right">Count</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.by_plan?.map((row, idx) => (
                  <tr key={idx}>
                    <td className="py-2">{row.plan__name || '—'}</td>
                    <td className="py-2">{row.status}</td>
                    <td className="py-2 text-right font-medium">{row.count}</td>
                  </tr>
                ))}
                {(!data?.by_plan || data.by_plan.length === 0) && (
                  <tr><td colSpan="3" className="py-6 text-center text-slate-400">No subscription data.</td></tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
              <Clock className="w-5 h-5 mr-2 text-accent-500" />
              Expiring in Next 7 Days
            </h2>
            <div className="space-y-3">
              {data?.expiring_soon?.map((s, idx) => (
                <div key={idx} className="flex justify-between items-center text-sm border-b border-slate-50 pb-2">
                  <div>
                    <p className="font-medium text-slate-900">{s.user_email}</p>
                    <p className="text-xs text-slate-500">{s.plan}</p>
                  </div>
                  <span className="text-xs text-orange-600 font-medium">
                    {new Date(s.expires_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
              {(!data?.expiring_soon || data.expiring_soon.length === 0) && (
                <p className="text-center text-slate-400 py-6">Nothing expiring soon.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <CaregiverSubscriptions />
    </div>
  );
}
