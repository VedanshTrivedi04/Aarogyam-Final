import { AgentBase } from './base.agent';
import { axiosInstance as api } from '@/lib/axios';

const CAREGIVER_BASE = '/caregivers';

class CaregiverAgent extends AgentBase {
  /** GET /api/v1/caregivers/patients/ */
  async getPatients() {
    return this._get(api.get(`${CAREGIVER_BASE}/patients/`));
  }

  /** POST /api/v1/caregivers/patients/add/ */
  async addPatient(payload) {
    return this._post(api.post(`${CAREGIVER_BASE}/patients/add/`, payload));
  }

  /** GET /api/v1/analytics/caregiver/summary/ */
  async getDashboardSummary() {
    return this._get(api.get('/analytics/caregiver/summary/'));
  }

  /** GET /api/v1/analytics/caregiver/cohort/ */
  async getPatientCohort() {
    return this._get(api.get('/analytics/caregiver/cohort/'));
  }

  /** GET /api/v1/caregivers/patients/:id/ */
  async getPatientDetails(patientId) {
    return this._get(api.get(`${CAREGIVER_BASE}/patients/${patientId}/`));
  }

  /** PATCH /api/v1/caregivers/patients/:id/ */
  async updatePatientDetails(patientId, payload) {
    return this._patch(api.patch(`${CAREGIVER_BASE}/patients/${patientId}/`, payload));
  }

  /** GET /api/v1/caregivers/patients/:id/adherence/summary/ */
  async getPatientAdherence(patientId) {
    return this._get(api.get(`${CAREGIVER_BASE}/patients/${patientId}/adherence/summary/`));
  }

  /** GET /api/v1/caregivers/patients/:id/alerts/ */
  async getPatientAlerts(patientId) {
    return this._get(api.get(`${CAREGIVER_BASE}/patients/${patientId}/alerts/`));
  }

  /** GET /api/v1/caregivers/patients/:id/prescriptions/ */
  async getPatientPrescriptions(patientId) {
    return this._get(api.get(`${CAREGIVER_BASE}/patients/${patientId}/prescriptions/`));
  }

  /**
   * POST /api/v1/caregivers/patients/:id/prescriptions/
   * payload: { medicine_name, dosage_value, dosage_unit, total_pills,
   *            compartment_number, duration_days, schedule_times, instructions }
   */
  async createPatientPrescription(patientId, payload) {
    return this._post(api.post(`${CAREGIVER_BASE}/patients/${patientId}/prescriptions/`, payload));
  }

  /** DELETE /api/v1/caregivers/patients/:id/prescriptions/:prescriptionId/ */
  async deletePatientPrescription(patientId, prescriptionId) {
    return this._delete(api.delete(`${CAREGIVER_BASE}/patients/${patientId}/prescriptions/${prescriptionId}/`));
  }

  /** GET /api/v1/caregivers/patients/:id/devices/ */
  async getPatientDevices(patientId) {
    return this._get(api.get(`${CAREGIVER_BASE}/patients/${patientId}/devices/`));
  }

  /**
   * PATCH /api/v1/caregivers/patients/:patientId/devices/:deviceId/compartments/:compartmentNumber/reschedule/
   * payload: { scheduled_time: 'HH:MM' }
   */
  async rescheduleCompartment(patientId, deviceId, compartmentNumber, payload) {
    const url = `${CAREGIVER_BASE}/patients/${patientId}/devices/${deviceId}/compartments/${compartmentNumber}/reschedule/`;
    return this._patch(api.patch(url, payload));
  }

  /** POST /api/v1/communications/rooms/ — get or create chat room with patient */
  async getOrCreateChatRoom(patientId) {
    return this._post(api.post('/communications/rooms/', { patient_id: patientId }));
  }

  /** GET /api/v1/communications/rooms/:id/messages/ — message history */
  async getChatMessages(roomId, beforeId = null) {
    const params = beforeId ? { before_id: beforeId } : {};
    return this._get(api.get(`/communications/rooms/${roomId}/messages/`, { params }));
  }
}

export const caregiverAgent = new CaregiverAgent();
