import { lazy, Suspense } from 'react';
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './guards/ProtectedRoute';
import { PatientLayout } from '@/components/layout/PatientLayout';

// Loading fallback
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[60vh] w-full">
    <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
  </div>
);

// Lazy loaded pages
const LandingPage = lazy(() => import('@/pages/public/LandingPage'));
const SmartDispenser = lazy(() => import('@/pages/public/SmartDispenser'));
const ConsultDoctors = lazy(() => import('@/pages/public/ConsultDoctors'));
const Login = lazy(() => import('@/pages/auth/Login'));
const Register = lazy(() => import('@/pages/auth/RegisterPage'));
const VerifyEmail = lazy(() => import('@/pages/auth/VerifyEmail'));
const Unauthorized = lazy(() => import('@/pages/auth/Unauthorized'));
const DemoPage = lazy(() => import('@/pages/public/DemoPage'));
const NotificationsCentre = lazy(() => import('@/pages/shared/NotificationsCentre'));
const SplashScreen = lazy(() => import('@/pages/shared/SplashScreen'));
const ProfilePage  = lazy(() => import('@/pages/shared/ProfilePage'));

// Patient Portal
const PatientHome = lazy(() => import('@/pages/patient/Home'));
const MedicineManagement = lazy(() => import('@/pages/patient/MedicineManagement'));
const Reports = lazy(() => import('@/pages/patient/Reports'));
const PatientSettings = lazy(() => import('@/pages/patient/Settings'));
const Conditions = lazy(() => import('@/pages/patient/Conditions'));
const Reminders = lazy(() => import('@/pages/patient/Reminders'));
const TakeMedicine = lazy(() => import('@/pages/patient/TakeMedicine'));
const DoseResult = lazy(() => import('@/pages/patient/DoseResult'));
const VitalsDashboard = lazy(() => import('@/pages/patient/VitalsDashboard'));
const Rewards = lazy(() => import('@/pages/patient/Rewards'));
const FamilyGroups = lazy(() => import('@/pages/patient/FamilyGroups'));
const Pharmacy = lazy(() => import('@/pages/patient/Pharmacy'));

// Caregiver Portal
const CaregiverHome = lazy(() => import('@/pages/caregiver/Home'));
const AlertsFeed = lazy(() => import('@/pages/caregiver/AlertsFeed'));
const CaregiverPatientDetail = lazy(() => import('@/pages/caregiver/PatientDetail'));
const CompartmentManager = lazy(() => import('@/pages/caregiver/CompartmentManager'));
const FillingMode = lazy(() => import('@/pages/caregiver/FillingMode'));
const RemoteUnlock = lazy(() => import('@/pages/caregiver/RemoteUnlock'));
const CaregiverSettings = lazy(() => import('@/pages/caregiver/Settings'));
const DeviceManager = lazy(() => import('@/pages/caregiver/DeviceManager'));
const MedicineManager = lazy(() => import('@/pages/caregiver/MedicineManager'));
const Geofencing = lazy(() => import('@/pages/caregiver/Geofencing'));

// Admin Portal
const AdminLayout = lazy(() => import('@/components/layout/AdminLayout').then(m => ({ default: m.AdminLayout })));
const AdminDashboard = lazy(() => import('@/pages/admin/Dashboard'));
const AdminUsers = lazy(() => import('@/pages/admin/Users'));
const AdminSubscriptions = lazy(() => import('@/pages/admin/Subscriptions'));
const AdminHardware = lazy(() => import('@/pages/admin/Hardware'));
const AdminSystemHealth = lazy(() => import('@/pages/admin/SystemHealth'));

// Super Admin Portal
const SuperAdminLayout = lazy(() => import('@/components/layout/SuperAdminLayout').then(m => ({ default: m.SuperAdminLayout })));
const SuperAdminDashboard = lazy(() => import('@/pages/super-admin/Dashboard'));
const SuperAdminPortalDetail = lazy(() => import('@/pages/super-admin/PortalDetail'));
const SuperAdminUsers = lazy(() => import('@/pages/super-admin/Users'));
const SuperAdminAuditLog = lazy(() => import('@/pages/super-admin/AuditLog'));
const SuperAdminTenants = lazy(() => import('@/pages/super-admin/Tenants'));
const SuperAdminBilling = lazy(() => import('@/pages/super-admin/Billing'));
const SuperAdminPharmacovigilance = lazy(() => import('@/pages/super-admin/Pharmacovigilance'));
const SuperAdminDevices = lazy(() => import('@/pages/super-admin/Devices'));
const SuperAdminNotifications = lazy(() => import('@/pages/super-admin/Notifications'));
const SuperAdminInsurance = lazy(() => import('@/pages/super-admin/Insurance'));
const SuperAdminGamification = lazy(() => import('@/pages/super-admin/Gamification'));
const SuperAdminGeofencing = lazy(() => import('@/pages/super-admin/Geofencing'));
const SuperAdminSystemHealthPage = lazy(() => import('@/pages/super-admin/SystemHealth'));
const SuperAdminAnalytics = lazy(() => import('@/pages/super-admin/Analytics'));

// Doctor Portal
const DoctorHome = lazy(() => import('@/pages/doctor/Home'));
const CriticalPanel = lazy(() => import('@/pages/doctor/CriticalPanel'));
const DoctorPatientDetail = lazy(() => import('@/pages/doctor/PatientDetail'));
const PrescribeMedicines = lazy(() => import('@/pages/doctor/PrescribeMedicines'));
const DoctorConsultations = lazy(() => import('@/pages/doctor/Consultations'));

// Patient — My Doctor
const MyDoctor = lazy(() => import('@/pages/patient/MyDoctor'));

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <Suspense fallback={<PageLoader />}>
        <LandingPage />
      </Suspense>
    ),
  },
  {
    path: '/splash',
    element: (
      <Suspense fallback={<PageLoader />}>
        <SplashScreen />
      </Suspense>
    ),
  },
  {
    path: '/notifications',
    element: (
      <Suspense fallback={<PageLoader />}>
        <NotificationsCentre />
      </Suspense>
    ),
  },
  {
    path: '/login',
    element: (
      <Suspense fallback={<PageLoader />}>
        <Login />
      </Suspense>
    ),
  },
  {
    path: '/register',
    element: (
      <Suspense fallback={<PageLoader />}>
        <Register />
      </Suspense>
    ),
  },
  {
    path: '/verify-email',
    element: (
      <Suspense fallback={<PageLoader />}>
        <VerifyEmail />
      </Suspense>
    ),
  },
  {
    path: '/unauthorized',
    element: (
      <Suspense fallback={<PageLoader />}>
        <Unauthorized />
      </Suspense>
    ),
  },
  // Backward-compatible redirect for old /dashboard links
  {
    path: '/dashboard',
    element: <Navigate to="/patient/home" replace />,
  },
  {
    path: '/dashboard/*',
    element: <Navigate to="/patient/home" replace />,
  },

  // Patient Portal Routes
  {
    path: '/patient',
    element: (
      <ProtectedRoute requiredRole="PATIENT">
        <PatientLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="home" replace />,
      },
      {
        path: 'home',
        element: (
          <Suspense fallback={<PageLoader />}>
            <PatientHome />
          </Suspense>
        ),
      },
      {
        path: 'medicines',
        element: (
          <Suspense fallback={<PageLoader />}>
            <MedicineManagement />
          </Suspense>
        ),
      },
      {
        path: 'reports',
        element: (
          <Suspense fallback={<PageLoader />}>
            <Reports />
          </Suspense>
        ),
      },
      {
        path: 'settings',
        element: (
          <Suspense fallback={<PageLoader />}>
            <PatientSettings />
          </Suspense>
        ),
      },
      {
        path: 'conditions',
        element: (
          <Suspense fallback={<PageLoader />}>
            <Conditions />
          </Suspense>
        ),
      },
      {
        path: 'reminders',
        element: (
          <Suspense fallback={<PageLoader />}>
            <Reminders />
          </Suspense>
        ),
      },
      {
        path: 'dose/:id',
        element: (
          <Suspense fallback={<PageLoader />}>
            <TakeMedicine />
          </Suspense>
        ),
      },
      {
        path: 'dose/:id/status',
        element: (
          <Suspense fallback={<PageLoader />}>
            <DoseResult />
          </Suspense>
        ),
      },
      {
        path: 'vitals',
        element: (
          <Suspense fallback={<PageLoader />}>
            <VitalsDashboard />
          </Suspense>
        ),
      },
      {
        path: 'rewards',
        element: (
          <Suspense fallback={<PageLoader />}>
            <Rewards />
          </Suspense>
        ),
      },
      {
        path: 'family',
        element: (
          <Suspense fallback={<PageLoader />}>
            <FamilyGroups />
          </Suspense>
        ),
      },
      {
        path: 'my-doctor',
        element: (
          <Suspense fallback={<PageLoader />}>
            <MyDoctor />
          </Suspense>
        ),
      },
      {
        path: 'profile',
        element: (
          <Suspense fallback={<PageLoader />}>
            <ProfilePage />
          </Suspense>
        ),
      },
    ],
  },

  // Caregiver Portal Routes
  {
    path: '/caregiver',
    element: (
      <ProtectedRoute requiredRole="CAREGIVER">
        <PatientLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="home" replace />,
      },
      {
        path: 'home',
        element: (
          <Suspense fallback={<PageLoader />}>
            <CaregiverHome />
          </Suspense>
        ),
      },
      {
        path: 'alerts',
        element: (
          <Suspense fallback={<PageLoader />}>
            <AlertsFeed />
          </Suspense>
        ),
      },
      {
        path: 'patient/:id',
        element: (
          <Suspense fallback={<PageLoader />}>
            <CaregiverPatientDetail />
          </Suspense>
        ),
      },
      {
        path: 'compartments',
        element: (
          <Suspense fallback={<PageLoader />}>
            <CompartmentManager />
          </Suspense>
        ),
      },
      {
        path: 'fill',
        element: (
          <Suspense fallback={<PageLoader />}>
            <FillingMode />
          </Suspense>
        ),
      },
      {
        path: 'unlock',
        element: (
          <Suspense fallback={<PageLoader />}>
            <RemoteUnlock />
          </Suspense>
        ),
      },
      {
        path: 'settings',
        element: (
          <Suspense fallback={<PageLoader />}>
            <CaregiverSettings />
          </Suspense>
        ),
      },
      {
        path: 'devices',
        element: (
          <Suspense fallback={<PageLoader />}>
            <DeviceManager />
          </Suspense>
        ),
      },
      {
        path: 'medicines',
        element: (
          <Suspense fallback={<PageLoader />}>
            <MedicineManager />
          </Suspense>
        ),
      },
      {
        path: 'geofencing',
        element: (
          <Suspense fallback={<PageLoader />}>
            <Geofencing />
          </Suspense>
        ),
      },
      {
        path: 'profile',
        element: (
          <Suspense fallback={<PageLoader />}>
            <ProfilePage />
          </Suspense>
        ),
      },
    ],
  },

  // Admin Portal Routes
  {
    path: '/admin',
    element: (
      <ProtectedRoute requiredRole="ADMIN">
        <Suspense fallback={<PageLoader />}>
          <AdminLayout />
        </Suspense>
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="home" replace />,
      },
      {
        path: 'home',
        element: (
          <Suspense fallback={<PageLoader />}>
            <AdminDashboard />
          </Suspense>
        ),
      },
      {
        path: 'users',
        element: (
          <Suspense fallback={<PageLoader />}>
            <AdminUsers />
          </Suspense>
        ),
      },
      {
        path: 'subscriptions',
        element: (
          <Suspense fallback={<PageLoader />}>
            <AdminSubscriptions />
          </Suspense>
        ),
      },
      {
        path: 'hardware',
        element: (
          <Suspense fallback={<PageLoader />}>
            <AdminHardware />
          </Suspense>
        ),
      },
      {
        path: 'health',
        element: (
          <Suspense fallback={<PageLoader />}>
            <AdminSystemHealth />
          </Suspense>
        ),
      },
    ],
  },

  // Super Admin Portal Routes
  {
    path: '/super-admin',
    element: (
      <ProtectedRoute requiredRole="SUPER_ADMIN">
        <Suspense fallback={<PageLoader />}>
          <SuperAdminLayout />
        </Suspense>
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminDashboard />
          </Suspense>
        ),
      },
      {
        path: 'portals/:portal',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminPortalDetail />
          </Suspense>
        ),
      },
      {
        path: 'users',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminUsers />
          </Suspense>
        ),
      },
      {
        path: 'audit',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminAuditLog />
          </Suspense>
        ),
      },
      {
        path: 'tenants',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminTenants />
          </Suspense>
        ),
      },
      {
        path: 'billing',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminBilling />
          </Suspense>
        ),
      },
      {
        path: 'pharmacovigilance',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminPharmacovigilance />
          </Suspense>
        ),
      },
      {
        path: 'devices',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminDevices />
          </Suspense>
        ),
      },
      {
        path: 'notifications',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminNotifications />
          </Suspense>
        ),
      },
      {
        path: 'insurance',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminInsurance />
          </Suspense>
        ),
      },
      {
        path: 'gamification',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminGamification />
          </Suspense>
        ),
      },
      {
        path: 'geofencing',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminGeofencing />
          </Suspense>
        ),
      },
      {
        path: 'system',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminSystemHealthPage />
          </Suspense>
        ),
      },
      {
        path: 'analytics',
        element: (
          <Suspense fallback={<PageLoader />}>
            <SuperAdminAnalytics />
          </Suspense>
        ),
      },
    ],
  },

  // Doctor Portal Routes
  {
    path: '/doctor',
    element: (
      <ProtectedRoute requiredRole="DOCTOR">
        <PatientLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="home" replace />,
      },
      {
        path: 'home',
        element: (
          <Suspense fallback={<PageLoader />}>
            <DoctorHome />
          </Suspense>
        ),
      },
      {
        path: 'critical',
        element: (
          <Suspense fallback={<PageLoader />}>
            <CriticalPanel />
          </Suspense>
        ),
      },
      {
        path: 'patient/:id',
        element: (
          <Suspense fallback={<PageLoader />}>
            <DoctorPatientDetail />
          </Suspense>
        ),
      },
      {
        path: 'prescribe/:id',
        element: (
          <Suspense fallback={<PageLoader />}>
            <PrescribeMedicines />
          </Suspense>
        ),
      },
      {
        path: 'consultations',
        element: (
          <Suspense fallback={<PageLoader />}>
            <DoctorConsultations />
          </Suspense>
        ),
      },
      {
        path: 'settings',
        element: (
          <Suspense fallback={<PageLoader />}>
            <PatientSettings />
          </Suspense>
        ),
      },
      {
        path: 'profile',
        element: (
          <Suspense fallback={<PageLoader />}>
            <ProfilePage />
          </Suspense>
        ),
      },
    ],
  },

  // Public/Other Routes
  {
    path: '/demo',
    element: (
      <Suspense fallback={<PageLoader />}>
        <DemoPage />
      </Suspense>
    ),
  },
  {
    path: '/smart-dispenser',
    element: (
      <Suspense fallback={<PageLoader />}>
        <SmartDispenser />
      </Suspense>
    ),
  },
  {
    path: '/consult-doctors',
    element: (
      <Suspense fallback={<PageLoader />}>
        <ConsultDoctors />
      </Suspense>
    ),
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

export const AppRouter = () => {
  return <RouterProvider router={router} />;
};
