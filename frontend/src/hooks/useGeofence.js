import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { geofenceAgent } from '@/agents/geofence.agent';

const geofenceKeys = {
  all: () => ['geofence'],
  zones: (patientId) => ['geofence', 'zones', patientId],
  events: (p) => ['geofence', 'events', p],
};

export const useGeofenceZones = (patientId) => {
  return useQuery({
    queryKey: geofenceKeys.zones(patientId),
    queryFn: () => geofenceAgent.getZones(patientId),
    enabled: !!patientId,
    select: (res) => Array.isArray(res) ? res : (res?.data ?? res?.results ?? []),
  });
};

export const useCreateGeofenceZone = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => geofenceAgent.createZone(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: geofenceKeys.all() }),
  });
};

export const useUpdateGeofenceZone = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }) => geofenceAgent.updateZone(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: geofenceKeys.all() }),
  });
};

export const useDeleteGeofenceZone = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => geofenceAgent.deleteZone(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: geofenceKeys.all() }),
  });
};

export const useGeofenceEvents = (params = {}) => {
  return useQuery({
    queryKey: geofenceKeys.events(params),
    queryFn: () => geofenceAgent.getEvents(params),
    enabled: !!params.patient_id,
    select: (res) => Array.isArray(res) ? res : (res?.data ?? res?.results ?? []),
  });
};
