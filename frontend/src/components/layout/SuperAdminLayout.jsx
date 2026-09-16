import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth.store';
import {
  LayoutDashboard,
  Users,
  ShieldCheck,
  Building2,
  CreditCard,
  FlaskConical,
  Cpu,
  MessageSquare,
  FileText,
  Trophy,
  MapPin,
  Activity,
  BarChart3,
  LogOut,
  Menu,
  X,
  Bell
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { name: 'Dashboard', path: '/super-admin/dashboard', icon: LayoutDashboard },
  { name: 'Users & Roles', path: '/super-admin/users', icon: Users },
  { name: 'Audit Log', path: '/super-admin/audit', icon: ShieldCheck },
  { name: 'Tenants', path: '/super-admin/tenants', icon: Building2 },
  { name: 'Billing', path: '/super-admin/billing', icon: CreditCard },
  { name: 'Pharmacovigilance', path: '/super-admin/pharmacovigilance', icon: FlaskConical },
  { name: 'Device Fleet', path: '/super-admin/devices', icon: Cpu },
  { name: 'Notifications', path: '/super-admin/notifications', icon: MessageSquare },
  { name: 'Insurance / Reports', path: '/super-admin/insurance', icon: FileText },
  { name: 'Gamification', path: '/super-admin/gamification', icon: Trophy },
  { name: 'Geofencing', path: '/super-admin/geofencing', icon: MapPin },
  { name: 'System Health', path: '/super-admin/system', icon: Activity },
  { name: 'Analytics', path: '/super-admin/analytics', icon: BarChart3 },
];

export function SuperAdminLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { user, clearSession } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    clearSession();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans">
      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-white border-b border-slate-200">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-accent-500/10 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-accent-500" />
          </div>
          <span className="font-bold text-lg text-slate-900 tracking-tight">Super Admin</span>
        </div>
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
        >
          {isSidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Sidebar */}
      <aside
        className={`
          fixed md:sticky top-0 z-40 h-screen w-64 bg-white border-r border-slate-200 shadow-sm
          transform transition-transform duration-300 ease-in-out flex flex-col
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        <div className="p-6 hidden md:flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-accent-500/10 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-accent-500" />
          </div>
          <span className="font-bold text-xl text-slate-900 tracking-tight">Super<span className="text-accent-500">Admin</span></span>
        </div>

        <div className="px-4 pb-2 mb-4 border-b border-slate-100 hidden md:block">
          <div className="text-sm font-medium text-slate-900 px-2">{user?.full_name || 'Super Admin'}</div>
          <div className="text-xs text-slate-500 px-2">{user?.email}</div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-3">Control Tower</div>
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              onClick={() => setIsSidebarOpen(false)}
              className={({ isActive }) => `
                flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
                ${isActive
                  ? 'bg-accent-500/10 text-accent-600'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }
              `}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-200">
          <button
            onClick={handleLogout}
            className="flex items-center w-full space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut className="w-5 h-5 flex-shrink-0" />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between hidden md:flex sticky top-0 z-30">
          <h1 className="text-xl font-semibold text-slate-800">Super Admin Control Tower</h1>
          <div className="flex items-center space-x-4">
            <button className="relative p-2 text-slate-400 hover:text-slate-600 transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-slate-50">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>

      {/* Mobile overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-slate-900/50 z-30 md:hidden backdrop-blur-sm"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}
    </div>
  );
}
