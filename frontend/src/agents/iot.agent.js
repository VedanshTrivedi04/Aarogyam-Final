import { AgentBase } from './base.agent';
import { axiosInstance as api } from '@/lib/axios';

const IOT_BASE = '/iot';

class IoTAgent extends AgentBase {
  // ── Device list & detail ─────────────────────────────────────────
  async getDevices() {
    return this._get(api.get(`${IOT_BASE}/devices/`));
  }

  async getDeviceDetail(deviceId) {
    return this._get(api.get(`${IOT_BASE}/devices/${deviceId}/`));
  }

  async updateDeviceDetail(deviceId, data) {
    return this._patch(api.patch(`${IOT_BASE}/devices/${deviceId}/`, data));
  }

  async linkPatientToDevice(deviceId, patientId) {
    return this._patch(api.patch(`${IOT_BASE}/devices/${deviceId}/link-patient/`, { patient_id: patientId ?? null }));
  }

  async deactivateDevice(deviceId) {
    return this._get(api.delete(`${IOT_BASE}/devices/${deviceId}/`));
  }

  async getDeviceStatus(deviceId) {
    return this._get(api.get(`${IOT_BASE}/devices/${deviceId}/status/`));
  }

  async getDeviceEvents(deviceId) {
    return this._get(api.get(`${IOT_BASE}/devices/${deviceId}/events/`));
  }

  // ── Device registration flow ─────────────────────────────────────
  async validateDeviceCode(uniqueCode) {
    return this._post(api.post(`${IOT_BASE}/devices/validate-code/`, { unique_code: uniqueCode }));
  }

  async linkDevice(deviceName, deviceType = 'CIRCULAR_PILL_DISPENSER', uniqueCode = null) {
    const body = { device_name: deviceName, device_type: deviceType };
    if (uniqueCode) body.unique_code = uniqueCode;
    return this._post(api.post(`${IOT_BASE}/devices/link/`, body));
  }

  // ── Legacy compartment mapping (DeviceCompartmentMapping) ─────────
  async getDeviceCompartments(deviceId) {
    return this._get(api.get(`${IOT_BASE}/devices/${deviceId}/compartments/`));
  }

  async updateDeviceCompartments(deviceId, compartments) {
    return this._post(api.put(`${IOT_BASE}/devices/${deviceId}/compartments/`, { compartments }));
  }

  async getDeviceInventory(deviceId) {
    return this._get(api.get(`${IOT_BASE}/devices/${deviceId}/inventory/`));
  }

  // ── Command queue ────────────────────────────────────────────────
  async queueCommand(deviceId, commandType, payload = {}, expiresInMinutes = 60) {
    return this._post(api.post(`${IOT_BASE}/devices/${deviceId}/commands/queue/`, {
      command_type: commandType,
      payload,
      expires_in_minutes: expiresInMinutes,
    }));
  }

  // ── Dispenser — 4-compartment PhysicalCompartment architecture ───

  /** POST /dispenser/setup/ — creates the 4 PhysicalCompartment rows (idempotent) */
  async setupDispenserCompartments(deviceId) {
    return this._post(api.post(`${IOT_BASE}/devices/${deviceId}/dispenser/setup/`));
  }

  /** GET /dispenser/compartments/ — returns PhysicalCompartment + sub_compartments */
  async getDispenserCompartments(deviceId) {
    return this._get(api.get(`${IOT_BASE}/devices/${deviceId}/dispenser/compartments/`));
  }

  /** POST /dispenser/compartments/{num}/medicine/add/ */
  async addMedicineToCompartment(deviceId, compartmentNum, data) {
    return this._post(api.post(
      `${IOT_BASE}/devices/${deviceId}/dispenser/compartments/${compartmentNum}/medicine/add/`,
      data,
    ));
  }

  /** GET /dispenser/compartments/{num}/medicines/ */
  async getMedicinesInCompartment(deviceId, compartmentNum) {
    return this._get(api.get(
      `${IOT_BASE}/devices/${deviceId}/dispenser/compartments/${compartmentNum}/medicines/`,
    ));
  }

  /** DELETE /dispenser/compartments/{num}/medicines/{medicineId}/ */
  async removeMedicineFromCompartment(deviceId, compartmentNum, medicineId) {
    return this._get(api.delete(
      `${IOT_BASE}/devices/${deviceId}/dispenser/compartments/${compartmentNum}/medicines/${medicineId}/`,
    ));
  }

  /** POST /dispenser/compartments/{num}/medicines/{medicineId}/measure-weight/ */
  async triggerWeightMeasure(deviceId, compartmentNum, medicineId) {
    return this._post(api.post(
      `${IOT_BASE}/devices/${deviceId}/dispenser/compartments/${compartmentNum}/medicines/${medicineId}/measure-weight/`,
    ));
  }

  /** POST /dispenser/fill/complete/ */
  async completeFill(deviceId, compartmentNumber = null) {
    const payload = compartmentNumber ? { compartment_number: compartmentNumber } : {};
    return this._post(api.post(`${IOT_BASE}/devices/${deviceId}/dispenser/fill/complete/`, payload));
  }

  /** PATCH /dispenser/compartments/{num}/time/ — update alarm time for a compartment */
  async updateCompartmentSlotTime(deviceId, compartmentNum, scheduledTime) {
    return this._patch(api.patch(
      `${IOT_BASE}/devices/${deviceId}/dispenser/compartments/${compartmentNum}/time/`,
      { scheduled_time: scheduledTime },
    ));
  }


  // ── Fill Mode (legacy — for DeviceCompartmentMapping-based flow) ──
  async startFillMode(deviceId, compartmentNumber = 1) {
    return this._post(api.post(`${IOT_BASE}/devices/${deviceId}/fill/start/`, { compartment_number: compartmentNumber }));
  }

  async nextFillMode(deviceId, currentCompartment, pillsAdded = 0) {
    return this._post(api.post(`${IOT_BASE}/devices/${deviceId}/fill/next/`, {
      current_compartment: currentCompartment,
      pills_added: pillsAdded,
    }));
  }

  async endFillMode(deviceId) {
    return this._post(api.post(`${IOT_BASE}/devices/${deviceId}/fill/end/`));
  }

  // ── Dose management ──────────────────────────────────────────────
  async getDoseAlerts() {
    return this._get(api.get(`${IOT_BASE}/dose/alerts/`));
  }

  async getDoseHistory(deviceId) {
    const params = deviceId ? `?device_id=${deviceId}` : '';
    return this._get(api.get(`${IOT_BASE}/dose/history/${params}`));
  }

  async getMissedDoses(deviceId) {
    const params = deviceId ? `?device_id=${deviceId}` : '';
    return this._get(api.get(`${IOT_BASE}/dose/missed/${params}`));
  }

  async unlockDevice(deviceId) {
    return this._post(api.post(`${IOT_BASE}/dose/caregiver-unlock/`, { device_id: deviceId }));
  }
}

export const iotAgent = new IoTAgent();
