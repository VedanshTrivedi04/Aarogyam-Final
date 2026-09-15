import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { userAgent } from '@/agents/user.agent';
import { axiosInstance } from '@/lib/axios';
import { qk, STALE } from './qk';

export function useUserProfile() {
  return useQuery({
    queryKey: qk.auth.me(),
    queryFn: () => userAgent.getMe(),
    staleTime: STALE.USER_PROFILE,
  });
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: ['user', 'notification-preferences'],
    queryFn: () => userAgent.getNotificationPreferences(),
    staleTime: STALE.USER_PROFILE,
  });
}

export function useUpdateUserProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => userAgent.updateMe(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.auth.me() });
    },
  });
}

export function useUploadAvatar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file) => userAgent.uploadAvatar(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.auth.me() });
    },
  });
}

export function useUpdateNotificationPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => userAgent.updateNotificationPreferences(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['user', 'notification-preferences'] });
    },
  });
}

export function usePatientProfile() {
  return useQuery({
    queryKey: ['patient', 'me'],
    queryFn: async () => {
      const res = await axiosInstance.get('/patients/me/');
      return res.data?.data ?? res.data;
    },
    staleTime: STALE.USER_PROFILE,
  });
}

export function useUpdatePatientProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data) => {
      const res = await axiosInstance.put('/patients/me/', data);
      return res.data?.data ?? res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patient', 'me'] });
    },
  });
}
