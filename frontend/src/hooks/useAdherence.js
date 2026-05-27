import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adherenceAgent } from '@/agents/adherence.agent';
import { qk, STALE } from './qk';

export const useTodaySchedule = (patientId) => useQuery({
  queryKey: qk.adherence.today(patientId),
  queryFn: () => adherenceAgent.getTodaySchedule(patientId),
  staleTime: STALE.TODAY_SCHEDULE,
  refetchInterval: 60_000, // auto-refresh every minute
});

export const useLogDose = (patientId) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (doseData) => adherenceAgent.logDose(doseData),
    onMutate: async (doseData) => {
      await queryClient.cancelQueries({ queryKey: qk.adherence.today(patientId) });
      const snapshot = queryClient.getQueryData(qk.adherence.today(patientId));
      
      queryClient.setQueryData(qk.adherence.today(patientId), (old) => {
        if (!old) return old;
        // Depending on backend structure, 'old' could be an array or { doses: [] }
        // TodayRemindersView returns an array directly: [ { id: '...', ... } ]
        if (Array.isArray(old)) {
          return old.map((d) => 
            d.id === doseData.reminderId
              ? { ...d, status: doseData.status || 'TAKEN' }
              : d
          );
        }
        // Fallback for wrapped response
        return {
          ...old,
          doses: (old.doses || []).map((d) =>
            d.id === doseData.reminderId
              ? { ...d, status: doseData.status || 'TAKEN' }
              : d
          ),
        };
      });
      
      if (navigator.vibrate) navigator.vibrate([50, 30, 100]);
      
      return { snapshot };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.adherence.streak(patientId) });
      queryClient.invalidateQueries({ queryKey: qk.ai.riskScore(patientId) });
      queryClient.invalidateQueries({ queryKey: qk.adherence.rate(patientId) });
    },
    onError: (error, variables, context) => {
      if (error.code !== 'ALREADY_LOGGED') {
        queryClient.setQueryData(qk.adherence.today(patientId), context.snapshot);
      }
    },
  });
};

export const useDispenseNow = () => {
  return useMutation({
    mutationFn: (reminderId) => adherenceAgent.dispenseNow(reminderId),
  });
};

export const useAdherenceRate = (patientId, days = 30) => useQuery({
  queryKey: qk.adherence.rate(patientId),
  queryFn: () => adherenceAgent.getAdherenceRate({ days, patientId }),
  staleTime: STALE.ADHERENCE_RATE,
});

export const useAdherenceHeatmap = (weeks = 16) => useQuery({
  queryKey: qk.adherence.heatmap(),
  queryFn: () => adherenceAgent.getHeatmap({ weeks }),
  staleTime: STALE.AI_INSIGHTS,
});

export const useStreak = (patientId) => useQuery({
  queryKey: qk.adherence.streak(patientId),
  queryFn: () => adherenceAgent.getStreak(),
  staleTime: STALE.TODAY_SCHEDULE,
});
