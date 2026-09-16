import { useState } from 'react';
import { useSuperAdminAuditLog } from '@/hooks/useSuperAdmin';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ShieldCheck, ChevronLeft, ChevronRight } from 'lucide-react';

export default function SuperAdminAuditLog() {
  const [action, setAction] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading, isFetching } = useSuperAdminAuditLog({
    action, resource_type: resourceType, page,
  });

  const rows = data?.results || [];

  const handleFilterChange = (setter) => (e) => {
    setter(e.target.value);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <ShieldCheck className="w-6 h-6 mr-2 text-accent-500" />
          Audit Log
        </h1>
        <p className="text-slate-500 mt-1">Immutable, HIPAA-compliant trail of every recorded action on the platform.</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Filter by action (e.g. USER_LOGIN)..."
          value={action}
          onChange={handleFilterChange(setAction)}
          className="flex-1 px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
        />
        <input
          type="text"
          placeholder="Filter by resource type (e.g. Prescription)..."
          value={resourceType}
          onChange={handleFilterChange(setResourceType)}
          className="flex-1 px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
        />
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
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Resource</th>
                  <th className="py-3 px-4">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 whitespace-nowrap text-slate-500">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">{log.actor_email || 'System'}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {log.resource_type}{log.resource_id ? ` #${log.resource_id.slice(0, 8)}` : ''}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{log.ip_address || '—'}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan="5" className="py-8 text-center text-slate-500">
                      No audit records found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
            <span className="text-xs text-slate-500">
              Page {data?.page || 1} — {data?.total || 0} total records
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                disabled={page <= 1 || isFetching}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
              >
                <ChevronLeft className="w-3 h-3 mr-1" /> Prev
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                disabled={!data?.has_next || isFetching}
                onClick={() => setPage((p) => p + 1)}
              >
                Next <ChevronRight className="w-3 h-3 ml-1" />
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
