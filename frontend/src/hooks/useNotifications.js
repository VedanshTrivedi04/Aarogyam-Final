import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { axiosInstance } from '@/lib/axios';
import { qk } from './qk';

/**
 * Fetch notifications for the logged in user
 */
export function useNotifications(params = {}) {
  return useQuery({
    queryKey: [...qk.notification.history(params.page || 1), params],
    queryFn: async () => {
      const res = await axiosInstance.get('/notifications/', { params });
      // The backend returns a paginated response with a list of results and unread_count
      const data = res.data?.results ?? res.data?.data?.results ?? res.data?.data ?? [];
      const unreadCount = res.data?.unread_count ?? res.data?.data?.unread_count ?? 0;
      return {
        results: Array.isArray(data) ? data : [],
        unreadCount,
      };
    },
    refetchInterval: 30_000, // Poll every 30s to keep it real-time
  });
}

/**
 * Mark a single notification as read with optimistic UI updates
 */
export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id) => {
      const res = await axiosInstance.patch(`/notifications/${id}/read/`);
      return res.data?.data ?? res.data;
    },
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['notification'] });
      const previousNotifications = qc.getQueriesData({ queryKey: ['notification'] });

      qc.setQueriesData({ queryKey: ['notification'] }, (old) => {
        if (!old || !Array.isArray(old.results)) return old;
        let wasUnread = false;
        const updatedResults = old.results.map((n) => {
          if (n.id === id) {
            if (!n.read_at && n.status !== 'READ') wasUnread = true;
            return { ...n, read_at: new Date().toISOString(), status: 'READ' };
          }
          return n;
        });

        return {
          ...old,
          results: updatedResults,
          unreadCount: Math.max(0, (old.unreadCount || 0) - (wasUnread ? 1 : 0)),
        };
      });

      return { previousNotifications };
    },
    onError: (_err, _id, context) => {
      if (context?.previousNotifications) {
        context.previousNotifications.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data);
        });
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['notification'] });
      qc.invalidateQueries({ queryKey: ['caregiver'] });
      qc.invalidateQueries({ queryKey: ['doctor'] });
    },
  });
}

/**
 * Mark all notifications as read with optimistic UI updates
 */
export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await axiosInstance.patch('/notifications/read-all/');
      return res.data?.data ?? res.data;
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ['notification'] });
      const previousNotifications = qc.getQueriesData({ queryKey: ['notification'] });

      qc.setQueriesData({ queryKey: ['notification'] }, (old) => {
        if (!old || !Array.isArray(old.results)) return old;
        const now = new Date().toISOString();
        const updatedResults = old.results.map((n) => ({
          ...n,
          read_at: n.read_at || now,
          status: 'READ',
        }));

        return {
          ...old,
          results: updatedResults,
          unreadCount: 0,
        };
      });

      return { previousNotifications };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousNotifications) {
        context.previousNotifications.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data);
        });
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['notification'] });
      qc.invalidateQueries({ queryKey: ['caregiver'] });
      qc.invalidateQueries({ queryKey: ['doctor'] });
    },
  });
}

/**
 * Delete a notification with optimistic removal
 */
export function useDeleteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id) => {
      const res = await axiosInstance.delete(`/notifications/${id}/`);
      return res.data;
    },
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['notification'] });
      const previousNotifications = qc.getQueriesData({ queryKey: ['notification'] });

      qc.setQueriesData({ queryKey: ['notification'] }, (old) => {
        if (!old || !Array.isArray(old.results)) return old;
        const target = old.results.find((n) => n.id === id);
        const wasUnread = target && !target.read_at && target.status !== 'READ';
        return {
          ...old,
          results: old.results.filter((n) => n.id !== id),
          unreadCount: Math.max(0, (old.unreadCount || 0) - (wasUnread ? 1 : 0)),
        };
      });

      return { previousNotifications };
    },
    onError: (_err, _id, context) => {
      if (context?.previousNotifications) {
        context.previousNotifications.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data);
        });
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['notification'] });
      qc.invalidateQueries({ queryKey: ['caregiver'] });
      qc.invalidateQueries({ queryKey: ['doctor'] });
    },
  });
}
