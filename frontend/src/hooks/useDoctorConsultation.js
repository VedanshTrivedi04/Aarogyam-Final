import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { doctorAgent } from '@/agents/doctor.agent';
import { qk } from './qk';

export function useConsultations() {
  return useQuery({
    queryKey: ['doctor-consultations'],
    queryFn: () => doctorAgent.getConsultations(),
  });
}

export function useAllDoctors() {
  return useQuery({
    queryKey: ['all-doctors'],
    queryFn: () => doctorAgent.getAllDoctors(),
  });
}

export function useMyDoctorPrescriptions() {
  return useQuery({
    queryKey: ['my-doctor-prescriptions'],
    queryFn: () => doctorAgent.getMyDoctorPrescriptions(),
  });
}

export function useRequestConsultation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (doctorProfileId) => doctorAgent.requestConsultation(doctorProfileId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['doctor-consultations'] }),
  });
}

export function useAcceptConsultation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId) => doctorAgent.acceptConsultation(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['doctor-consultations'] }),
  });
}

export function useRejectConsultation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId) => doctorAgent.rejectConsultation(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['doctor-consultations'] }),
  });
}

export function useEndConsultation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, notes }) => doctorAgent.endConsultation(sessionId, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['doctor-consultations'] }),
  });
}

export function useRespondToPrescription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ prescriptionId, accepted }) => doctorAgent.respondToPrescription(prescriptionId, accepted),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-doctor-prescriptions'] }),
  });
}

export function useSetAvailability() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (isAvailable) => doctorAgent.setAvailability(isAvailable),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.doctor.profile() }),
  });
}

/** Doctor asks to view the patient's adherence report — needs patient approval. */
export function useRequestAdherenceReport() {
  return useMutation({
    mutationFn: (sessionId) => doctorAgent.requestAdherenceReport(sessionId),
  });
}

/** Patient approves/denies an adherence-report request. */
export function useRespondAdherenceRequest() {
  return useMutation({
    mutationFn: ({ sessionId, requestId, approved }) =>
      doctorAgent.respondAdherenceRequest(sessionId, requestId, approved),
  });
}
