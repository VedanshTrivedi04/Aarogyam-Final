import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { iotAgent } from '@/agents/iot.agent';

// ── Shared query key builder ─────────────────────────────────────────────────
const iotKey = {
  devices: () => ['iot', 'devices'],
  device: (id) => ['iot', 'device', id],
  status: (id) => ['iot', 'device', id, 'status'],
  events: (id) => ['iot', 'device', id, 'events'],
  compartments: (id) => ['iot', 'device', id, 'compartments'],
  inventory: (id) => ['iot', 'device', id, 'inventory'],
  dispenserCompartments: (id) => ['iot', 'device', id, 'dispenser-compartments'],
  doseAlerts: () => ['iot', 'dose', 'alerts'],
  doseHistory: (id) => ['iot', 'dose', 'history', id ?? 'all'],
  missedDoses: (id) => ['iot', 'dose', 'missed', id ?? 'all'],
};

// ── Device list ──────────────────────────────────────────────────────────────
export function useCaregiverDevices() {
  return useQuery({
    queryKey: iotKey.devices(),
    queryFn: () => iotAgent.getDevices(),
    staleTime: 30_000,
  });
}

// ── Device detail & status ───────────────────────────────────────────────────
export function useDeviceDetail(deviceId) {
  return useQuery({
    queryKey: iotKey.device(deviceId),
    queryFn: () => iotAgent.getDeviceDetail(deviceId),
    enabled: !!deviceId,
    staleTime: 30_000,
  });
}

export function useUpdateDeviceDetail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, data }) => iotAgent.updateDeviceDetail(deviceId, data),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
    },
  });
}

export function useLinkPatientToDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, patientId }) => iotAgent.linkPatientToDevice(deviceId, patientId),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
    },
  });
}

export function useDeviceStatus(deviceId) {
  return useQuery({
    queryKey: iotKey.status(deviceId),
    queryFn: () => iotAgent.getDeviceStatus(deviceId),
    enabled: !!deviceId,
    staleTime: 15_000,
    refetchInterval: 30_000,   // poll every 30s for live badge
  });
}

export function useDeviceEvents(deviceId) {
  return useQuery({
    queryKey: iotKey.events(deviceId),
    queryFn: () => iotAgent.getDeviceEvents(deviceId),
    enabled: !!deviceId,
    staleTime: 15_000,
  });
}

// ── Device registration ──────────────────────────────────────────────────────
export function useValidateDeviceCode() {
  return useMutation({
    mutationFn: (code) => iotAgent.validateDeviceCode(code),
  });
}

export function useLinkDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceName, deviceType, uniqueCode }) => iotAgent.linkDevice(deviceName, deviceType, uniqueCode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: iotKey.devices() });
    },
  });
}

export function useDeactivateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deviceId) => iotAgent.deactivateDevice(deviceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: iotKey.devices() });
    },
  });
}

// ── Legacy compartment mapping ───────────────────────────────────────────────
export function useDeviceCompartments(deviceId) {
  return useQuery({
    queryKey: iotKey.compartments(deviceId),
    queryFn: () => iotAgent.getDeviceCompartments(deviceId),
    enabled: !!deviceId,
    staleTime: 15_000,
  });
}

export function useDeviceInventory(deviceId) {
  return useQuery({
    queryKey: iotKey.inventory(deviceId),
    queryFn: () => iotAgent.getDeviceInventory(deviceId),
    enabled: !!deviceId,
    staleTime: 15_000,
  });
}

export function useUpdateDeviceCompartments() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, compartments }) => iotAgent.updateDeviceCompartments(deviceId, compartments),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
      qc.invalidateQueries({ queryKey: iotKey.dispenserCompartments(deviceId) });
      qc.invalidateQueries({ queryKey: ['caregiver', 'patients'] });
    },
  });
}

// ── Commands ─────────────────────────────────────────────────────────────────
export function useQueueCommand() {
  return useMutation({
    mutationFn: ({ deviceId, commandType, payload, expiresInMinutes }) =>
      iotAgent.queueCommand(deviceId, commandType, payload, expiresInMinutes),
  });
}

// ── Fill Mode (legacy) ───────────────────────────────────────────────────────
export function useStartFillMode() {
  return useMutation({
    mutationFn: ({ deviceId, compartmentNumber }) => iotAgent.startFillMode(deviceId, compartmentNumber),
  });
}

export function useNextFillMode() {
  return useMutation({
    mutationFn: ({ deviceId, currentCompartment, pillsAdded }) =>
      iotAgent.nextFillMode(deviceId, currentCompartment, pillsAdded),
  });
}

export function useEndFillMode() {
  return useMutation({
    mutationFn: (deviceId) => iotAgent.endFillMode(deviceId),
  });
}

// ── Dispenser — New 4-Compartment Architecture ───────────────────────────────
export function useSetupDispenserCompartments() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deviceId) => iotAgent.setupDispenserCompartments(deviceId),
    onSuccess: (_data, deviceId) => {
      qc.invalidateQueries({ queryKey: iotKey.dispenserCompartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
      qc.invalidateQueries({ queryKey: ['caregiver', 'patients'] });
    },
  });
}

export function useDispenserCompartments(deviceId) {
  return useQuery({
    queryKey: iotKey.dispenserCompartments(deviceId),
    queryFn: () => iotAgent.getDispenserCompartments(deviceId),
    enabled: !!deviceId,
    staleTime: 20_000,
  });
}

export function useAddMedicineToCompartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, compartmentNum, data }) =>
      iotAgent.addMedicineToCompartment(deviceId, compartmentNum, data),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.dispenserCompartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.inventory(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.compartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
      qc.invalidateQueries({ queryKey: ['caregiver', 'patients'] });
    },
  });
}

export function useRemoveMedicineFromCompartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, compartmentNum, medicineId }) =>
      iotAgent.removeMedicineFromCompartment(deviceId, compartmentNum, medicineId),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.dispenserCompartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.inventory(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.compartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
      qc.invalidateQueries({ queryKey: ['caregiver', 'patients'] });
    },
  });
}

export function useTriggerWeightMeasure() {
  return useMutation({
    mutationFn: ({ deviceId, compartmentNum, medicineId }) =>
      iotAgent.triggerWeightMeasure(deviceId, compartmentNum, medicineId),
  });
}

export function useCompleteFill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, compartmentNumber }) => iotAgent.completeFill(deviceId, compartmentNumber),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.dispenserCompartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.inventory(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.devices() });
      qc.invalidateQueries({ queryKey: ['caregiver', 'patients'] });
    },
  });
}

// Update a single compartment's scheduled alarm time (new dispenser system)
export function useUpdateCompartmentSlotTime() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, compartmentNum, scheduledTime }) =>
      iotAgent.updateCompartmentSlotTime(deviceId, compartmentNum, scheduledTime),
    onSuccess: (_data, { deviceId }) => {
      qc.invalidateQueries({ queryKey: iotKey.dispenserCompartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.compartments(deviceId) });
      qc.invalidateQueries({ queryKey: iotKey.device(deviceId) });
    },
  });
}


// ── Dose management ──────────────────────────────────────────────────────────
export function useDoseAlerts() {
  return useQuery({
    queryKey: iotKey.doseAlerts(),
    queryFn: () => iotAgent.getDoseAlerts(),
    staleTime: 15_000,
    refetchInterval: 60_000,
  });
}

export function useUnlockDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deviceId) => iotAgent.unlockDevice(deviceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: iotKey.doseAlerts() });
    },
  });
}

export function useDoseHistory(deviceId) {
  return useQuery({
    queryKey: iotKey.doseHistory(deviceId),
    queryFn: () => iotAgent.getDoseHistory(deviceId),
    staleTime: 30_000,
  });
}

export function useMissedDoses(deviceId) {
  return useQuery({
    queryKey: iotKey.missedDoses(deviceId),
    queryFn: () => iotAgent.getMissedDoses(deviceId),
    enabled: !!deviceId,
    staleTime: 20_000,
  });
}
