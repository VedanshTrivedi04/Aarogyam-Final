import { useState } from 'react';
import {
  useSuperAdminTenants,
  useSuperAdminCreateTenant,
  useSuperAdminAssignTenantAdmin,
  useSuperAdminSetTenantStatus,
} from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Building2, Plus, CheckCircle, ShieldAlert, UserPlus } from 'lucide-react';

const PLANS = ['CLINIC', 'HOSPITAL', 'ENTERPRISE'];

export default function SuperAdminTenants() {
  const { data: tenants, isLoading } = useSuperAdminTenants();
  const createTenant = useSuperAdminCreateTenant();
  const assignAdmin = useSuperAdminAssignTenantAdmin();
  const setStatus = useSuperAdminSetTenantStatus();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', subdomain: '', plan: 'CLINIC' });
  const [assigningId, setAssigningId] = useState(null);
  const [assignUserId, setAssignUserId] = useState('');

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await createTenant.mutateAsync(form);
      setForm({ name: '', subdomain: '', plan: 'CLINIC' });
      setShowForm(false);
    } catch {
      alert('Failed to create tenant — check the subdomain is unique.');
    }
  };

  const handleAssign = async (tenantId) => {
    if (!assignUserId) return;
    try {
      await assignAdmin.mutateAsync({ tenantId, user_id: assignUserId });
      setAssigningId(null);
      setAssignUserId('');
    } catch {
      alert('Failed to assign admin — check the user ID.');
    }
  };

  const handleToggleStatus = async (tenant) => {
    const action = tenant.is_active ? 'deactivate' : 'activate';
    if (window.confirm(`Are you sure you want to ${action} "${tenant.name}"?`)) {
      await setStatus.mutateAsync({ tenantId: tenant.id, is_active: !tenant.is_active });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center">
            <Building2 className="w-6 h-6 mr-2 text-accent-500" />
            Tenants
          </h1>
          <p className="text-slate-500 mt-1">Manage clinic/hospital tenants — Super Admin exclusive.</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)} className="h-10 text-sm">
          <Plus className="w-4 h-4 mr-1" /> New Tenant
        </Button>
      </div>

      {showForm && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
                <input
                  type="text" required value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Subdomain</label>
                <input
                  type="text" required value={form.subdomain}
                  onChange={(e) => setForm((f) => ({ ...f, subdomain: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Plan</label>
                <select
                  value={form.plan}
                  onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
                >
                  {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <Button type="submit" disabled={createTenant.isPending} className="h-10 text-sm">
                {createTenant.isPending ? 'Creating...' : 'Create Tenant'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : (
        <Card className="border-slate-200/60 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
                <tr>
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Subdomain</th>
                  <th className="py-3 px-4">Plan</th>
                  <th className="py-3 px-4">Admins</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tenants?.map((tenant) => (
                  <tr key={tenant.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900">{tenant.name}</td>
                    <td className="py-3 px-4 text-slate-500">{tenant.subdomain}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                        {tenant.plan}
                      </span>
                    </td>
                    <td className="py-3 px-4">{tenant.admin_count}</td>
                    <td className="py-3 px-4">
                      {tenant.is_active ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-700">
                          <CheckCircle className="w-3 h-3 mr-1" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-red-100 text-red-700">
                          <ShieldAlert className="w-3 h-3 mr-1" /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2 whitespace-nowrap">
                      {assigningId === tenant.id ? (
                        <span className="inline-flex items-center gap-1">
                          <input
                            type="text"
                            placeholder="User ID"
                            value={assignUserId}
                            onChange={(e) => setAssignUserId(e.target.value)}
                            className="w-32 px-2 py-1 text-xs border border-slate-300 rounded-md"
                          />
                          <Button size="sm" className="h-7 text-xs" onClick={() => handleAssign(tenant.id)} disabled={assignAdmin.isPending}>
                            Save
                          </Button>
                        </span>
                      ) : (
                        <Button
                          variant="outline" size="sm" className="h-7 text-xs"
                          onClick={() => { setAssigningId(tenant.id); setAssignUserId(''); }}
                        >
                          <UserPlus className="w-3 h-3 mr-1" /> Add Admin
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className={`h-7 text-xs border-0 ${
                          tenant.is_active
                            ? 'bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700'
                            : 'bg-green-50 text-green-600 hover:bg-green-100 hover:text-green-700'
                        }`}
                        onClick={() => handleToggleStatus(tenant)}
                        disabled={setStatus.isPending}
                      >
                        {tenant.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                    </td>
                  </tr>
                ))}
                {tenants?.length === 0 && (
                  <tr>
                    <td colSpan="6" className="py-8 text-center text-slate-500">
                      No tenants yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
