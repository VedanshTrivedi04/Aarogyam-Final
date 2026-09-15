import { AgentBase } from './base.agent';
import { axiosInstance as api } from '@/lib/axios';

const AI_BASE = '/ai';

class AiAgent extends AgentBase {
  async getRiskScore(patientId = 'me') {
    return this._get(api.get(`${AI_BASE}/risk-score/${patientId}/`));
  }

  async getInsights(patientId = 'me') {
    return this._get(api.get(`${AI_BASE}/insights/${patientId}/`));
  }

  async getRecommendations(patientId = 'me') {
    return this._get(api.get(`${AI_BASE}/recommendations/${patientId}/`));
  }

  async getAgentActivity(patientId = 'me') {
    return this._get(api.get(`/agent-runtime/activity/${patientId}/`));
  }
}

export const aiAgent = new AiAgent();
