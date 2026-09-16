import { useParams, Link } from 'react-router-dom';
import { useSuperAdminPortalDetail } from '@/hooks/useSuperAdmin';
import { Card } from '@/components/ui/Card';
import { ArrowLeft } from 'lucide-react';

const PORTAL_LABELS = {
  PATIENT: 'Patient Portal',
  CAREGIVER: 'Caregiver Portal',
  DOCTOR: 'Doctor Portal',
  PHARMACY: 'Pharmacy Portal',
};

const PHARMACY_COLUMNS = [
  { key: 'patient', label: 'Patient' },
  { key: 'medication', label: 'Medication' },
  { key: 'status', label: 'Status' },
  { key: 'quantity_ordered', label: 'Qty' },
  { key: 'total_amount', label: 'Amount' },
  { key: 'estimated_delivery', label: 'Est. Delivery' },
];

const MISSED_DOSE_COLUMNS = [
  { key: 'patient', label: 'Patient' },
  { key: 'medication', label: 'Medication' },
  { key: 'scheduled_at', label: 'Scheduled At' },
  { key: 'dose_value', label: 'Dose' },
  { key: 'status', label: 'Status' },
];

function formatCell(key, value) {
  if (value == null || value === '') return '—';
  if (key === 'scheduled_at' || key === 'estimated_delivery') {
    return new Date(value).toLocaleString();
  }
  return value;
}

export default function SuperAdminPortalDetail() {
  const { portal } = useParams();
  const portalKey = (portal || '').toUpperCase();
  const { data, isLoading } = useSuperAdminPortalDetail(portalKey);

  const columns = portalKey === 'PHARMACY' ? PHARMACY_COLUMNS : MISSED_DOSE_COLUMNS;
  const rows = data?.rows || [];

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/super-admin/dashboard"
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-slate-900 mb-3 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Dashboard
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">
          {PORTAL_LABELS[portalKey] || 'Portal'} — Detail
        </h1>
        <p className="text-slate-500 mt-1">
          {portalKey === 'PHARMACY'
            ? 'Recent refill orders across the platform.'
            : 'Recent missed doses driving this portal\'s alert count.'}
        </p>
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
                  {columns.map((col) => (
                    <th key={col.key} className="py-3 px-6">{col.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50/50 transition-colors">
                    {columns.map((col) => (
                      <td key={col.key} className="py-3 px-6">
                        {formatCell(col.key, row[col.key])}
                      </td>
                    ))}
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={columns.length} className="py-8 text-center text-slate-500">
                      No records found.
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
