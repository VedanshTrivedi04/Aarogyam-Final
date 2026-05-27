import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import { caregiverAgent } from '@/agents/caregiver.agent';
import { iotAgent } from '@/agents/iot.agent';
import { qk, STALE } from './qk';

/** Link a new patient to this caregiver */
export function useAddCaregiverPatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => caregiverAgent.addPatient(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.caregiver.patients() });
      qc.invalidateQueries({ queryKey: ['analytics', 'caregiver'] });
    }
  });
}

/** List all patients linked to this caregiver */
export function useCaregiverPatients() {
  return useQuery({
    queryKey: qk.caregiver.patients(),
    queryFn: () => caregiverAgent.getPatients(),
    staleTime: STALE.MEDICATION_LIST,
    select: (res) => {
      const raw = Array.isArray(res) ? res : (res?.data ?? res?.results ?? []);
      return raw.map(p => ({
        id: p.id,
        patientCode: p.patient_code,
        name: p.full_name || 'Unknown Patient',
        email: p.email,
        timezone: p.timezone,
        isHospitalized: p.is_hospitalized,
        activeMedsCount: p.active_meds || 0,
        permission: p.permission || 'view_only',
        // defaults
        conditions: [],
        meds: [],
        adherence: 0,
        streak: 0,
        lastDose: '--',
        status: p.is_hospitalized ? 'needs-attention' : 'on-track',
        avatar: (p.full_name || '?')[0].toUpperCase(),
        color: 'from-blue-500 to-cyan-500',
        riskScore: 'Low',
        location: p.timezone || 'Unknown',
        relation: 'Patient' // Add relation if available via links
      }));
    }
  });
}

/** Get detail for a specific patient */
export function useCaregiverPatientDetail(patientId) {
  return useQuery({
    queryKey: [...qk.caregiver.patients(), patientId, 'detail'],
    queryFn: () => caregiverAgent.getPatientDetails(patientId),
    enabled: !!patientId,
    staleTime: STALE.USER_PROFILE,
  });
}

/** Update specific patient detail */
export function useUpdateCaregiverPatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ patientId, payload }) => caregiverAgent.updatePatientDetails(patientId, payload),
    onSuccess: (_, { patientId }) => {
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), patientId, 'detail'] });
      qc.invalidateQueries({ queryKey: qk.caregiver.patients() });
    }
  });
}

/** Get adherence data for a specific patient */
export function useCaregiverPatientAdherence(patientId) {
  return useQuery({
    queryKey: [...qk.caregiver.patients(), patientId, 'adherence'],
    queryFn: () => caregiverAgent.getPatientAdherence(patientId),
    enabled: !!patientId,
    staleTime: STALE.ADHERENCE_SUMMARY,
  });
}

/** Get alerts for a specific patient */
export function useCaregiverPatientAlerts(patientId) {
  return useQuery({
    queryKey: [...qk.caregiver.patients(), patientId, 'alerts'],
    queryFn: () => caregiverAgent.getPatientAlerts(patientId),
    enabled: !!patientId,
    staleTime: STALE.ADHERENCE_SUMMARY, // roughly same freshness needed
  });
}

/** List prescriptions for a patient (requires manage_schedule+ permission) */
export function useCaregiverPatientPrescriptions(patientId) {
  return useQuery({
    queryKey: [...qk.caregiver.patients(), patientId, 'prescriptions'],
    queryFn: () => caregiverAgent.getPatientPrescriptions(patientId),
    enabled: !!patientId,
    staleTime: STALE.MEDICATION_LIST,
    select: (res) => Array.isArray(res) ? res : (res?.data ?? res?.results ?? []),
  });
}

/** Create a prescription + schedule for a patient */
export function useCreateCaregiverPrescription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ patientId, payload }) => caregiverAgent.createPatientPrescription(patientId, payload),
    onSuccess: (_, { patientId }) => {
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), patientId, 'prescriptions'] });
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), patientId, 'devices'] });
      qc.invalidateQueries({ queryKey: qk.iot.devices() });
    },
  });
}

/** Delete a prescription from a patient */
export function useDeleteCaregiverPrescription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ patientId, prescriptionId }) => caregiverAgent.deletePatientPrescription(patientId, prescriptionId),
    onSuccess: (_, { patientId }) => {
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), patientId, 'prescriptions'] });
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), patientId, 'devices'] });
      qc.invalidateQueries({ queryKey: qk.iot.devices() });
    },
  });
}

/** Get IoT devices linked to a patient (with compartment mapping) */
export function useCaregiverPatientDevices(patientId) {
  return useQuery({
    queryKey: [...qk.caregiver.patients(), patientId, 'devices'],
    queryFn: () => caregiverAgent.getPatientDevices(patientId),
    enabled: !!patientId,
    staleTime: 30_000,
    select: (res) => Array.isArray(res) ? res : (res?.data ?? res?.results ?? []),
  });
}

/** Reschedule a compartment time (caregiver action) */
export function useRescheduleCompartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ patientId, deviceId, compartmentNumber, payload }) => caregiverAgent.rescheduleCompartment(patientId, deviceId, compartmentNumber, payload),
    onSuccess: async (_, vars) => {
      // Keep existing invalidations for prescriptions/devices
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), vars.patientId, 'prescriptions'] });
      qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), vars.patientId, 'devices'] });
      qc.invalidateQueries({ queryKey: qk.iot.devices() });
      qc.invalidateQueries({ queryKey: qk.iot.device(vars.deviceId) });
      qc.invalidateQueries({ queryKey: qk.iot.dispenserCompartments(vars.deviceId) });
      qc.invalidateQueries({ queryKey: qk.iot.compartments(vars.deviceId) });
      qc.invalidateQueries({ queryKey: qk.iot.inventory(vars.deviceId) });

      // Try to refresh device compartments specifically so UI updates immediately
      try {
        const compartments = await iotAgent.getDeviceCompartments(vars.deviceId);
        // Update the cached devices list by merging compartments into the matching device
        qc.setQueryData([...qk.caregiver.patients(), vars.patientId, 'devices'], old => {
          if (!old) return old;
          return old.map(d => d.id === vars.deviceId ? ({ ...d, compartments }) : d);
        });
      } catch (e) {
        // Fallback: invalidate full devices list so it refetches
        qc.invalidateQueries({ queryKey: [...qk.caregiver.patients(), vars.patientId, 'devices'] });
      }
    }
  });
}

/** Pre-fetch adherence and alerts for a list of patients */
export function useCaregiverPatientsData(patientIds = []) {
  const adherenceQueries = useQueries({
    queries: patientIds.map(id => ({
      queryKey: [...qk.caregiver.patients(), id, 'adherence'],
      queryFn: () => caregiverAgent.getPatientAdherence(id),
      staleTime: STALE.ADHERENCE_SUMMARY,
    }))
  });

  const alertsQueries = useQueries({
    queries: patientIds.map(id => ({
      queryKey: [...qk.caregiver.patients(), id, 'alerts'],
      queryFn: () => caregiverAgent.getPatientAlerts(id),
      staleTime: STALE.ADHERENCE_SUMMARY,
    }))
  });

  return { adherenceQueries, alertsQueries };
}
