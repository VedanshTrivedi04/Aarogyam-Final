import { AgentBase } from './base.agent';
import { axiosInstance as api } from '@/lib/axios';

const DOCTOR_BASE = '/doctor';

class DoctorAgent extends AgentBase {
  // ── Doctor profile & patients ─────────────────────────────────────────────
  async getProfile() {
    return this._get(api.get(`${DOCTOR_BASE}/profiles/`));
  }

  /** POST /profiles/availability/ — doctor toggles "accepting calls/consults" */
  async setAvailability(isAvailable) {
    return this._post(api.post(`${DOCTOR_BASE}/profiles/availability/`, { is_available: isAvailable }));
  }

  async getLinkedPatients() {
    return this._get(api.get(`${DOCTOR_BASE}/links/`));
  }

  async getPatientAdherence(linkId) {
    return this._get(api.get(`${DOCTOR_BASE}/links/${linkId}/adherence/`));
  }

  async getPatientAlerts(linkId) {
    return this._get(api.get(`${DOCTOR_BASE}/links/${linkId}/alerts/`));
  }

  // ── Digital prescriptions ─────────────────────────────────────────────────
  async getDigitalPrescriptions() {
    return this._get(api.get(`${DOCTOR_BASE}/prescriptions/`));
  }

  /** Patient calls this to see their own received prescriptions */
  async getMyDoctorPrescriptions() {
    return this._get(api.get(`${DOCTOR_BASE}/prescriptions/`));
  }

  async createDigitalPrescription(data) {
    return this._post(api.post(`${DOCTOR_BASE}/prescriptions/`, data));
  }

  /** PATCH /prescriptions/{id}/accept/ — patient accepts or rejects */
  async respondToPrescription(prescriptionId, accepted) {
    return this._patch(api.patch(`${DOCTOR_BASE}/prescriptions/${prescriptionId}/accept/`, { accepted }));
  }

  // ── Consultation sessions ─────────────────────────────────────────────────
  /** GET /consultations/ — list sessions (filtered by role on backend) */
  async getConsultations() {
    return this._get(api.get(`${DOCTOR_BASE}/consultations/`));
  }

  /** GET /consultations/{id}/ */
  async getConsultation(sessionId) {
    return this._get(api.get(`${DOCTOR_BASE}/consultations/${sessionId}/`));
  }

  /** POST /consultations/ — patient requests a session with a doctor */
  async requestConsultation(doctorProfileId) {
    return this._post(api.post(`${DOCTOR_BASE}/consultations/`, { doctor: doctorProfileId }));
  }

  /** POST /consultations/{id}/accept/ — doctor accepts */
  async acceptConsultation(sessionId) {
    return this._post(api.post(`${DOCTOR_BASE}/consultations/${sessionId}/accept/`));
  }

  /** POST /consultations/{id}/reject/ — doctor rejects */
  async rejectConsultation(sessionId) {
    return this._post(api.post(`${DOCTOR_BASE}/consultations/${sessionId}/reject/`));
  }

  /** POST /consultations/{id}/end/ — doctor ends session */
  async endConsultation(sessionId, notes = '') {
    return this._post(api.post(`${DOCTOR_BASE}/consultations/${sessionId}/end/`, { notes }));
  }

  /** GET /consultations/{id}/messages/ — full chat history */
  async getConsultationMessages(sessionId) {
    return this._get(api.get(`${DOCTOR_BASE}/consultations/${sessionId}/messages/`));
  }

  /** POST /consultations/{id}/request-adherence/ — doctor asks to view the report */
  async requestAdherenceReport(sessionId) {
    return this._post(api.post(`${DOCTOR_BASE}/consultations/${sessionId}/request-adherence/`));
  }

  /** POST /consultations/{id}/respond-adherence/ — patient approves/denies */
  async respondAdherenceRequest(sessionId, requestId, approved) {
    return this._post(api.post(`${DOCTOR_BASE}/consultations/${sessionId}/respond-adherence/`, {
      request_id: requestId, approved,
    }));
  }

  // ── All verified doctors (for patient to browse) ──────────────────────────
  async getAllDoctors() {
    return this._get(api.get(`${DOCTOR_BASE}/profiles/`));
  }
}

export const doctorAgent = new DoctorAgent();
