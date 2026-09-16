import { useState } from 'react';
import { useSuperAdminPharmacovigilance } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { FlaskConical, AlertOctagon } from 'lucide-react';

const SEVERITIES = ['MILD', 'MODERATE', 'SEVERE', 'LIFE_THREATENING'];

const SEVERITY_STYLE = {
  MILD: 'bg-blue-100 text-blue-700',
  MODERATE: 'bg-orange-100 text-orange-700',
  SEVERE: 'bg-red-100 text-red-700',
  LIFE_THREATENING: 'bg-red-600 text-white',
};

export default function SuperAdminPharmacovigilance() {
  const [severity, setSeverity] = useState('');
  const { data, isLoading } = useSuperAdminPharmacovigilance({ severity });

  const counts = data?.severity_counts || {};
  const rows = data?.rows || [];

  const statCards = [
    { title: 'Mild', value: counts.mild || 0, color: 'text-blue-600', bgColor: 'bg-blue-50' },
    { title: 'Moderate', value: counts.moderate || 0, color: 'text-orange-600', bgColor: 'bg-orange-50' },
    { title: 'Severe', value: counts.severe || 0, color: 'text-red-600', bgColor: 'bg-red-50' },
    { title: 'Life Threatening', value: counts.life_threatening || 0, color: 'text-red-700', bgColor: 'bg-red-100' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <FlaskConical className="w-6 h-6 mr-2 text-accent-500" />
          Pharmacovigilance & Safety Alerts
        </h1>
        <p className="text-slate-500 mt-1">Side-effect reports across every patient, triaged by severity.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {statCards.map((stat, idx) => (
          <Card key={idx} className="border-slate-200/60 shadow-sm">
            <CardContent className="p-6">
              <p className="text-sm font-medium text-slate-500 mb-1">{stat.title}</p>
              <h3 className={`text-3xl font-bold ${stat.color}`}>{stat.value}</h3>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-3">
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-accent-500 focus:border-accent-500 sm:text-sm"
        >
          <option value="">All Severities</option>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
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
                  <th className="py-3 px-4">Patient</th>
                  <th className="py-3 px-4">Medication</th>
                  <th className="py-3 px-4">Symptom</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Onset</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900">{r.patient}</td>
                    <td className="py-3 px-4">{r.medication}</td>
                    <td className="py-3 px-4">{r.symptom}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${SEVERITY_STYLE[r.severity] || 'bg-slate-100 text-slate-700'}`}>
                        {r.severity === 'LIFE_THREATENING' && <AlertOctagon className="w-3 h-3 mr-1" />}
                        {r.severity.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">{new Date(r.onset_at).toLocaleDateString()}</td>
                    <td className="py-3 px-4">
                      {r.is_ongoing ? (
                        <span className="text-orange-600 font-medium">Ongoing</span>
                      ) : (
                        <span className="text-emerald-600 font-medium">Resolved</span>
                      )}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan="6" className="py-8 text-center text-slate-500">
                      No side effect reports found.
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
