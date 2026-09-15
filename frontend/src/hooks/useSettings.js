import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { axiosInstance } from '@/lib/axios';

// ─── Account Security ─────────────────────────────────────────────────────────

export function useSessions() {
  return useQuery({
    queryKey: ['user', 'sessions'],
    queryFn: async () => {
      const res = await axiosInstance.get('/users/me/sessions/');
      const d = res.data?.data ?? res.data;
      return Array.isArray(d) ? d : [];
    },
    staleTime: 30_000,
  });
}

export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id) => {
      await axiosInstance.delete(`/users/me/sessions/${id}/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user', 'sessions'] }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (data) => {
      try {
        const res = await axiosInstance.post('/auth/password/change/', data);
        return res.data?.data ?? res.data;
      } catch (err) {
        const message = err.response?.data?.error?.message || err.message || 'Failed to change password.';
        throw new Error(message, { cause: err });
      }
    },
  });
}

// ─── Subscription Plan ────────────────────────────────────────────────────────

export function useCurrentSubscription() {
  return useQuery({
    queryKey: ['subscription', 'current'],
    queryFn: async () => {
      const res = await axiosInstance.get('/subscriptions/current/');
      return res.data?.data ?? null;
    },
    staleTime: 60_000,
  });
}

export function useSubscriptionPlans() {
  return useQuery({
    queryKey: ['subscription', 'plans'],
    queryFn: async () => {
      const res = await axiosInstance.get('/subscriptions/plans/');
      const d = res.data?.data ?? res.data;
      return Array.isArray(d) ? d : [];
    },
    staleTime: 5 * 60_000,
  });
}

// Loads the Razorpay checkout script once, returns a promise that resolves when ready
function loadRazorpayScript() {
  return new Promise((resolve) => {
    if (window.Razorpay) { resolve(true); return; }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload  = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export function useUpgradeSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (planId) => {
      // Step 1: create Razorpay order on backend
      const orderRes = await axiosInstance.post('/subscriptions/create-order/', { plan_id: planId });
      const order    = orderRes.data?.data ?? orderRes.data;

      // Step 2: load Razorpay script
      const loaded = await loadRazorpayScript();
      if (!loaded) throw new Error('Razorpay SDK failed to load. Check your internet connection.');

      // Step 3: open Razorpay checkout modal and wait for result
      return new Promise((resolve, reject) => {
        const rzp = new window.Razorpay({
          key:         order.key_id,
          amount:      order.amount,
          currency:    order.currency,
          order_id:    order.order_id,
          name:        'MedAdhere',
          description: `${order.plan_name} Subscription`,
          prefill: {
            name:  order.user_name,
            email: order.user_email,
          },
          theme: { color: '#0ea5e9' },
          handler: async (response) => {
            try {
              // Step 4: verify payment on backend
              const verifyRes = await axiosInstance.post('/subscriptions/verify-payment/', {
                plan_id:              planId,
                razorpay_order_id:    response.razorpay_order_id,
                razorpay_payment_id:  response.razorpay_payment_id,
                razorpay_signature:   response.razorpay_signature,
              });
              resolve(verifyRes.data?.data ?? verifyRes.data);
            } catch (err) {
              reject(err);
            }
          },
          modal: {
            ondismiss: () => reject(new Error('Payment cancelled.')),
          },
        });
        rzp.open();
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscription'] }),
  });
}

export function useCancelSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await axiosInstance.post('/subscriptions/cancel/');
      return res.data?.data ?? res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscription'] }),
  });
}

export function useSubscriptionInvoices() {
  return useQuery({
    queryKey: ['subscription', 'invoices'],
    queryFn: async () => {
      const res = await axiosInstance.get('/subscriptions/invoices/');
      const d = res.data?.data ?? res.data;
      return Array.isArray(d) ? d : [];
    },
    staleTime: 60_000,
  });
}

export function useEmailInvoice() {
  return useMutation({
    mutationFn: async (invoiceId) => {
      const res = await axiosInstance.post(`/subscriptions/invoices/${invoiceId}/email/`);
      return res.data?.data ?? res.data;
    },
  });
}

// ─── Data Privacy (Notification Prefs) ───────────────────────────────────────

export function useNotificationPrefs() {
  return useQuery({
    queryKey: ['user', 'notification-preferences'],
    queryFn: async () => {
      const res = await axiosInstance.get('/users/me/notifications/');
      return res.data?.data ?? res.data ?? {};
    },
    staleTime: 60_000,
  });
}

export function useUpdateNotificationPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data) => {
      const res = await axiosInstance.patch('/users/me/notifications/', data);
      return res.data?.data ?? res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user', 'notification-preferences'] }),
  });
}

// ─── Medicine Archives ────────────────────────────────────────────────────────

export function useAllPrescriptions() {
  return useQuery({
    queryKey: ['prescription', 'all'],
    queryFn: async () => {
      const res = await axiosInstance.get('/patients/me/prescriptions/');
      const d = res.data?.data ?? res.data;
      return Array.isArray(d) ? d : [];
    },
    staleTime: 30_000,
  });
}
