import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { axiosInstance } from '@/lib/axios';

const SUPER_ADMIN_API = '/admin/super';

export const superAdminApi = {
  getOverview: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/overview/`);
    return data?.data || data;
  },
  getPortalBreakdown: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/portals/`);
    return data?.data || data;
  },
  getPortalDetail: async (portal) => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/portals/${portal}/detail/`);
    return data?.data || data;
  },
  getUsers: async ({ role, search } = {}) => {
    const params = {};
    if (role) params.role = role;
    if (search) params.search = search;
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/users/`, { params });
    return data?.data || data;
  },
  changeUserRole: async ({ id, role }) => {
    const { data } = await axiosInstance.patch(`${SUPER_ADMIN_API}/users/${id}/role/`, { role });
    return data?.data || data;
  },
  setUserStatus: async ({ id, is_active }) => {
    const { data } = await axiosInstance.patch(`${SUPER_ADMIN_API}/users/${id}/status/`, { is_active });
    return data?.data || data;
  },
  getAuditLog: async ({ action, resource_type, page } = {}) => {
    const params = {};
    if (action) params.action = action;
    if (resource_type) params.resource_type = resource_type;
    if (page) params.page = page;
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/audit/`, { params });
    return data?.data || data;
  },
  getTenants: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/tenants/`);
    return data?.data || data;
  },
  createTenant: async (payload) => {
    const { data } = await axiosInstance.post(`${SUPER_ADMIN_API}/tenants/`, payload);
    return data?.data || data;
  },
  assignTenantAdmin: async ({ tenantId, user_id, is_primary }) => {
    const { data } = await axiosInstance.post(`${SUPER_ADMIN_API}/tenants/${tenantId}/admins/`, { user_id, is_primary });
    return data?.data || data;
  },
  setTenantStatus: async ({ tenantId, is_active }) => {
    const { data } = await axiosInstance.patch(`${SUPER_ADMIN_API}/tenants/${tenantId}/status/`, { is_active });
    return data?.data || data;
  },
  getBillingOverview: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/billing/`);
    return data?.data || data;
  },
  getCaregiverSubscriptions: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/billing/caregivers/`);
    return data?.data || data;
  },
  assignCaregiverSubscription: async ({ userId, plan_slug, days }) => {
    const { data } = await axiosInstance.post(`${SUPER_ADMIN_API}/billing/caregivers/${userId}/subscription/`, { plan_slug, days });
    return data?.data || data;
  },
  extendCaregiverSubscription: async ({ userId, days }) => {
    const { data } = await axiosInstance.patch(`${SUPER_ADMIN_API}/billing/caregivers/${userId}/subscription/extend/`, { days });
    return data?.data || data;
  },
  cancelCaregiverSubscription: async ({ userId }) => {
    const { data } = await axiosInstance.patch(`${SUPER_ADMIN_API}/billing/caregivers/${userId}/subscription/cancel/`);
    return data?.data || data;
  },
  getPharmacovigilance: async ({ severity, reported_to_cdsco } = {}) => {
    const params = {};
    if (severity) params.severity = severity;
    if (reported_to_cdsco !== undefined && reported_to_cdsco !== '') params.reported_to_cdsco = reported_to_cdsco;
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/pharmacovigilance/`, { params });
    return data?.data || data;
  },
  getDeviceFleet: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/devices/`);
    return data?.data || data;
  },
  getNotificationsCenter: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/notifications-center/`);
    return data?.data || data;
  },
  getInsuranceReports: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/insurance/`);
    return data?.data || data;
  },
  getGamification: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/gamification/`);
    return data?.data || data;
  },
  getGeofencing: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/geofencing/`);
    return data?.data || data;
  },
  getSystemHealth: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/system/`);
    return data?.data || data;
  },
  getAnalytics: async () => {
    const { data } = await axiosInstance.get(`${SUPER_ADMIN_API}/analytics/`);
    return data?.data || data;
  },
};

export const useSuperAdminOverview = () => {
  return useQuery({
    queryKey: ['super-admin-overview'],
    queryFn: superAdminApi.getOverview,
  });
};

export const useSuperAdminPortals = () => {
  return useQuery({
    queryKey: ['super-admin-portals'],
    queryFn: superAdminApi.getPortalBreakdown,
  });
};

export const useSuperAdminPortalDetail = (portal) => {
  return useQuery({
    queryKey: ['super-admin-portal-detail', portal],
    queryFn: () => superAdminApi.getPortalDetail(portal),
    enabled: !!portal,
  });
};

export const useSuperAdminUsers = ({ role, search } = {}) => {
  return useQuery({
    queryKey: ['super-admin-users', role, search],
    queryFn: () => superAdminApi.getUsers({ role, search }),
  });
};

export const useSuperAdminChangeUserRole = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.changeUserRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-users'] });
    },
  });
};

export const useSuperAdminSetUserStatus = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.setUserStatus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-users'] });
    },
  });
};

export const useSuperAdminAuditLog = ({ action, resource_type, page } = {}) => {
  return useQuery({
    queryKey: ['super-admin-audit', action, resource_type, page],
    queryFn: () => superAdminApi.getAuditLog({ action, resource_type, page }),
    placeholderData: keepPreviousData,
  });
};

export const useSuperAdminTenants = () => {
  return useQuery({
    queryKey: ['super-admin-tenants'],
    queryFn: superAdminApi.getTenants,
  });
};

export const useSuperAdminCreateTenant = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.createTenant,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-tenants'] });
    },
  });
};

export const useSuperAdminAssignTenantAdmin = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.assignTenantAdmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-tenants'] });
    },
  });
};

export const useSuperAdminSetTenantStatus = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.setTenantStatus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-tenants'] });
    },
  });
};

export const useSuperAdminBilling = () => {
  return useQuery({
    queryKey: ['super-admin-billing'],
    queryFn: superAdminApi.getBillingOverview,
  });
};

export const useSuperAdminCaregiverSubscriptions = () => {
  return useQuery({
    queryKey: ['super-admin-caregiver-subs'],
    queryFn: superAdminApi.getCaregiverSubscriptions,
  });
};

export const useSuperAdminAssignCaregiverSubscription = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.assignCaregiverSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-caregiver-subs'] });
    },
  });
};

export const useSuperAdminExtendCaregiverSubscription = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.extendCaregiverSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-caregiver-subs'] });
    },
  });
};

export const useSuperAdminCancelCaregiverSubscription = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: superAdminApi.cancelCaregiverSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-caregiver-subs'] });
    },
  });
};

export const useSuperAdminPharmacovigilance = ({ severity, reported_to_cdsco } = {}) => {
  return useQuery({
    queryKey: ['super-admin-pharmacovigilance', severity, reported_to_cdsco],
    queryFn: () => superAdminApi.getPharmacovigilance({ severity, reported_to_cdsco }),
  });
};

export const useSuperAdminDeviceFleet = () => {
  return useQuery({
    queryKey: ['super-admin-devices'],
    queryFn: superAdminApi.getDeviceFleet,
  });
};

export const useSuperAdminNotificationsCenter = () => {
  return useQuery({
    queryKey: ['super-admin-notifications-center'],
    queryFn: superAdminApi.getNotificationsCenter,
  });
};

export const useSuperAdminInsuranceReports = () => {
  return useQuery({
    queryKey: ['super-admin-insurance'],
    queryFn: superAdminApi.getInsuranceReports,
  });
};

export const useSuperAdminGamification = () => {
  return useQuery({
    queryKey: ['super-admin-gamification'],
    queryFn: superAdminApi.getGamification,
  });
};

export const useSuperAdminGeofencing = () => {
  return useQuery({
    queryKey: ['super-admin-geofencing'],
    queryFn: superAdminApi.getGeofencing,
  });
};

export const useSuperAdminSystemHealth = () => {
  return useQuery({
    queryKey: ['super-admin-system'],
    queryFn: superAdminApi.getSystemHealth,
  });
};

export const useSuperAdminAnalytics = () => {
  return useQuery({
    queryKey: ['super-admin-analytics'],
    queryFn: superAdminApi.getAnalytics,
  });
};
