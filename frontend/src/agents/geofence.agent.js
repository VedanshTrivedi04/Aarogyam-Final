import { AgentBase } from './base.agent';
import { axiosInstance as api } from '@/lib/axios';

const BASE = '/geofence';

class GeofenceAgent extends AgentBase {
  async getZones(patientId) {
    return this._get(api.get(`${BASE}/zones/`, { params: { patient_id: patientId } }));
  }

  async createZone(data) {
    return this._post(api.post(`${BASE}/zones/`, data));
  }

  async updateZone(id, data) {
    return this._put(api.put(`${BASE}/zones/${id}/`, data));
  }

  async deleteZone(id) {
    return this._delete(api.delete(`${BASE}/zones/${id}/`));
  }

  async getEvents(params = {}) {
    return this._get(api.get(`${BASE}/zones/events/`, { params }));
  }
}

export const geofenceAgent = new GeofenceAgent();
