import { useQuery } from '@tanstack/react-query';
import { axiosInstance } from '@/lib/axios';
import { qk, STALE } from './qk';

export function useAdherenceTimeline(days = 30, patientId = null) {
  return useQuery({
    queryKey: [qk.adherence.heatmap(patientId || 'me'), days],
    queryFn: async () => {
      const url = patientId ? `/caregivers/patients/${patientId}/adherence/timeline/` : '/adherence/timeline/';
      const res = await axiosInstance.get(url, { params: { days } });
      return res.data?.data ?? res.data;
    },
    staleTime: STALE.AI_INSIGHTS,
  });
}

export function useAdherenceSummary(days = 30, patientId = null) {
  return useQuery({
    queryKey: [qk.adherence.rate(patientId || 'me'), days],
    queryFn: async () => {
      const url = patientId ? `/caregivers/patients/${patientId}/adherence/summary/` : '/adherence/summary/';
      const res = await axiosInstance.get(url, { params: { days } });
      return res.data?.data ?? res.data;
    },
    staleTime: STALE.ADHERENCE_RATE,
  });
}

export function useMedicationBreakdown(days = 30, patientId = null) {
  return useQuery({
    queryKey: ['adherence', 'medication-breakdown', patientId || 'me', days],
    queryFn: async () => {
      const url = patientId ? `/caregivers/patients/${patientId}/adherence/medications/` : '/adherence/medications/';
      const res = await axiosInstance.get(url, { params: { days } });
      return res.data?.data ?? res.data;
    },
    staleTime: STALE.AI_INSIGHTS,
  });
}

export function useExportAdherenceReport(patientId = null) {
  return async ({ days = 30, format = 'pdf' } = {}) => {
    const isValidId = patientId && patientId !== 'undefined' && patientId !== 'null' && patientId !== 'me';
    const url = isValidId
      ? `/caregivers/patients/${patientId}/adherence/export/`
      : '/adherence/export/';
    try {
      const res = await axiosInstance.get(url, {
        params: { days, export_format: format },
        responseType: 'blob',
      });
      return res;
    } catch (error) {
      // When responseType is 'blob', axios returns the error body as a Blob.
      // We must read it as text to extract the real error message.
      const raw = error?.response?.data;
      if (raw instanceof Blob) {
        try {
          const text = await raw.text();
          const parsed = JSON.parse(text);
          const msg =
            parsed?.error?.message ||
            parsed?.detail ||
            parsed?.message ||
            `Export failed (HTTP ${error?.response?.status ?? 'unknown'})`;
          throw new Error(msg);
        } catch (parseErr) {
          if (parseErr instanceof SyntaxError) {
            throw new Error(`Export failed (HTTP ${error?.response?.status ?? 'unknown'})`);
          }
          throw parseErr;
        }
      }
      // Non-blob error (network, etc.)
      throw new Error(
        error?.response?.data?.error?.message ||
        error?.message ||
        'Export failed'
      );
    }
  };
}
