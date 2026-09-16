import { useState } from 'react';
import {
  useSuperAdminUsers,
  useSuperAdminChangeUserRole,
  useSuperAdminSetUserStatus,
} from '@/hooks/useSuperAdmin';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ShieldAlert, UserX, UserCheck, CheckCircle, Clock, Search } from 'lucide-react';

const ROLES = ['PATIENT', 'DOCTOR', 'CAREGIVER', 'NURSE', 'PHARMACIST', 'ADMIN', 'SUPER_ADMIN'];

export default function SuperAdminUsers() {
  const [role, setRole] = useState('');
  const [search, setSearch] = useState('');
  const { data: users, isLoading } = useSuperAdminUsers({ role, search });
  const changeRole = useSuperAdminChangeUserRole();
  const setStatus = useSuperAdminSetUserStatus();

  const handleRoleChange = async (userId, newRole) => {
    if (window.confirm(`Change this user's role to ${newRole}?`)) {
      await changeRole.mutateAsync({ id: userId, role: newRole });
    }
  };

  const handleToggleStatus = async (user) => {
    const action = user.is_active ? 'deactivate' : 'activate';
    if (window.confirm(`Are you sure you want to ${action} this user?`)) {
      await setStatus.mutateAsync({ id: user.id, is_active: !user.is_active });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Users & Roles</h1>
        <p className="text-slate-500 mt-1">Full cross-role directory — change roles, activate or deactivate any account.</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
          />
        </div>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
        >
          <option value="">All Roles</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

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
                  <th className="py-3 px-4">Name / Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Joined</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users?.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900">{user.full_name || 'No Name'}</div>
                      <div className="text-xs text-slate-500">{user.email}</div>
                    </td>
                    <td className="py-3 px-4">
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value)}
                        disabled={changeRole.isPending}
                        className="text-xs font-medium bg-slate-100 text-slate-700 rounded-md px-2 py-1 border-0 focus:ring-accent-500"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      <div className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(user.date_joined).toLocaleDateString()}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {user.is_active ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-700">
                          <CheckCircle className="w-3 h-3 mr-1" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-red-100 text-red-700">
                          <ShieldAlert className="w-3 h-3 mr-1" /> Deactivated
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        variant="destructive"
                        size="sm"
                        className={`h-8 text-xs border-0 ${
                          user.is_active
                            ? 'bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700'
                            : 'bg-green-50 text-green-600 hover:bg-green-100 hover:text-green-700'
                        }`}
                        onClick={() => handleToggleStatus(user)}
                        disabled={setStatus.isPending}
                      >
                        {user.is_active ? (
                          <><UserX className="w-3 h-3 mr-1" /> Deactivate</>
                        ) : (
                          <><UserCheck className="w-3 h-3 mr-1" /> Activate</>
                        )}
                      </Button>
                    </td>
                  </tr>
                ))}
                {users?.length === 0 && (
                  <tr>
                    <td colSpan="5" className="py-8 text-center text-slate-500">
                      No users found.
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
