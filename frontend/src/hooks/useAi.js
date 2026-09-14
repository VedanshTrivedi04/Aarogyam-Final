import { useQuery } from '@tanstack/react-query';
import { aiAgent } from '@/agents/ai.agent';
import { qk, STALE } from './qk';

export const useRiskScore = (patientId = 'me') => {
  return useQuery({
    queryKey: qk.ai.riskScore(patientId),
    queryFn: () => aiAgent.getRiskScore(patientId),
    staleTime: STALE.RISK_SCORE,
    enabled: Boolean(patientId),
  });
};

export const useInsights = (patientId = 'me') => {
  return useQuery({
    queryKey: qk.ai.insights(patientId),
    queryFn: () => aiAgent.getInsights(patientId),
    staleTime: STALE.AI_INSIGHTS,
    enabled: Boolean(patientId),
  });
};

export const useRecommendations = (patientId = 'me') => {
  return useQuery({
    queryKey: ['ai', 'recommendations', patientId],
    queryFn: () => aiAgent.getRecommendations(patientId),
    staleTime: STALE.AI_INSIGHTS,
    enabled: Boolean(patientId),
  });
};

