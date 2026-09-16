import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Bell, 
  Search, 
  CheckCircle2, 
  CheckCheck,
  Check,
  AlertTriangle, 
  ShieldAlert,
  Trash2,
  Loader2,
  MessageSquare,
  ArrowLeft
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { 
  useNotifications, 
  useMarkNotificationRead, 
  useMarkAllNotificationsRead,
  useDeleteNotification 
} from '@/hooks/useNotifications';

const getCategory = (type) => {
  if (['DOSE_MISSED', 'MISSED_DOSE_ALERT', 'CAREGIVER_ALERT', 'ANOMALY_ALERT', 'DOCTOR_ALERT'].includes(type)) return 'critical';
  if (['REFILL_ALERT', 'PRESCRIPTION_EXPIRY', 'SUBSCRIPTION_EXPIRY'].includes(type)) return 'warning';
  return 'info';
};

function timeAgo(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now - date) / 1000);
  
  if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours}h ago`;
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 7) return `${diffInDays}d ago`;
  return date.toLocaleDateString();
}

function Toast({ msg, ok = true }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-5 py-3 rounded-2xl shadow-xl text-sm font-semibold text-white ${
        ok ? 'bg-emerald-600 shadow-emerald-600/20' : 'bg-destructive shadow-destructive/20'
      }`}
    >
      {ok ? <CheckCircle2 className="w-4 h-4 text-white" /> : <AlertTriangle className="w-4 h-4 text-white" />}
      <span>{msg}</span>
    </motion.div>
  );
}

const NotificationCard = ({ notification, onRead, onDelete, isMarking, isDeleting }) => {
  const getIcon = () => {
    switch (notification.category) {
      case 'critical': return <ShieldAlert className="w-5 h-5 text-destructive" />;
      case 'warning': return <AlertTriangle className="w-5 h-5 text-accent" />;
      case 'info': return <Bell className="w-5 h-5 text-primary" />;
      default: return <CheckCircle2 className="w-5 h-5 text-success" />;
    }
  };

  const getBg = () => {
    if (!notification.unread) return 'bg-card border-border/50 hover:border-primary/30';
    switch (notification.category) {
      case 'critical': return 'bg-destructive/5 border-destructive/30';
      case 'warning': return 'bg-accent/5 border-accent/30';
      default: return 'bg-primary/5 border-primary/30';
    }
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`p-5 rounded-2xl border transition-all group ${getBg()}`}
    >
      <div className="flex gap-4 items-start">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 
          ${notification.unread ? 'bg-white shadow-sm border border-border/40' : 'bg-muted/50 text-muted-foreground'}`}>
          {getIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-2 truncate">
              <h4 className={`font-bold text-sm truncate ${notification.unread ? 'text-foreground' : 'text-muted-foreground'}`}>
                {notification.title}
              </h4>
              {notification.unread && (
                <span className="w-2 h-2 rounded-full bg-primary shrink-0 animate-pulse" />
              )}
            </div>
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider shrink-0">{notification.time}</span>
          </div>
          <p className={`text-sm leading-relaxed mb-3 ${notification.unread ? 'text-foreground/90' : 'text-muted-foreground'}`}>
            {notification.message}
          </p>
          
          <div className="flex items-center justify-between gap-3 pt-1 flex-wrap">
            <div>
              {notification.action && (
                <Button variant={notification.category === 'critical' ? 'danger' : 'secondary'} size="sm" className="h-8 px-4 text-[10px] font-black uppercase tracking-widest rounded-lg">
                  {notification.action}
                </Button>
              )}
            </div>

            <div className="flex items-center gap-2 ml-auto">
              {notification.unread ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRead(notification.id)}
                  disabled={isMarking}
                  className="h-8 px-3 rounded-xl border-primary/30 text-primary hover:bg-primary/10 text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm"
                  title="Mark as read"
                >
                  {isMarking ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                  )}
                  <span>Mark as read</span>
                </Button>
              ) : (
                <span className="flex items-center gap-1 text-[11px] font-bold text-muted-foreground/70 bg-muted/40 px-2.5 py-1 rounded-lg border border-border/40">
                  <Check className="w-3 h-3 text-emerald-500" /> Read
                </span>
              )}

              <button 
                onClick={() => onDelete(notification.id)} 
                disabled={isDeleting}
                className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40" 
                title="Delete notification"
              >
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default function NotificationsCentre() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [toast, setToast] = useState(null);
  const [activeActionId, setActiveActionId] = useState(null);

  const { data: { results: apiNotifications = [], unreadCount: apiUnreadCount } = {}, isLoading } = useNotifications();
  const markReadMut = useMarkNotificationRead();
  const markAllReadMut = useMarkAllNotificationsRead();
  const deleteNotifMut = useDeleteNotification();

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const notifications = apiNotifications.map(n => ({
    id: n.id,
    type: n.notification_type,
    title: n.title,
    message: n.body,
    time: timeAgo(n.created_at || n.sent_at),
    unread: !n.read_at && n.status !== 'READ',
    category: getCategory(n.notification_type),
    action: n.data?.action_label || null
  }));

  const markRead = (id) => {
    setActiveActionId(id);
    markReadMut.mutate(id, {
      onSuccess: () => {
        showToast('Notification marked as read.');
      },
      onError: (err) => {
        showToast(err?.response?.data?.message || 'Failed to mark as read.', false);
      },
      onSettled: () => {
        setActiveActionId(null);
      }
    });
  };

  const markAllRead = () => {
    markAllReadMut.mutate(undefined, {
      onSuccess: () => {
        showToast('All notifications marked as read.');
      },
      onError: (err) => {
        showToast(err?.response?.data?.message || 'Failed to mark all as read.', false);
      }
    });
  };

  const deleteNotification = (id) => {
    setActiveActionId(id);
    deleteNotifMut.mutate(id, {
      onSuccess: () => {
        showToast('Notification removed.');
      },
      onError: (err) => {
        showToast(err?.response?.data?.message || 'Failed to delete notification.', false);
      },
      onSettled: () => {
        setActiveActionId(null);
      }
    });
  };

  const filtered = notifications.filter(n => {
    if (searchQuery && !n.title.toLowerCase().includes(searchQuery.toLowerCase()) && !n.message.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (filter === 'all') return true;
    if (filter === 'unread') return n.unread;
    return n.category === filter;
  });

  const unreadCount = apiUnreadCount ?? notifications.filter(n => n.unread).length;

  return (
    <div className="flex flex-col gap-8 py-4 max-w-4xl mx-auto px-4">
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && <Toast msg={toast.msg} ok={toast.ok} />}
      </AnimatePresence>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <button 
            onClick={() => navigate(-1)} 
            className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground hover:text-primary transition-colors mb-2"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-3xl font-display font-bold text-foreground tracking-tight">Notifications & Alerts</h2>
            {unreadCount > 0 && (
              <Badge variant="primary" className="h-6 px-2.5 font-bold animate-pulse">{unreadCount} New</Badge>
            )}
          </div>
          <p className="text-muted-foreground font-medium text-sm">Stay updated with clinical alerts, reminders, and device status.</p>
        </div>

        <Button 
          onClick={markAllRead} 
          disabled={unreadCount === 0 || markAllReadMut.isPending}
          variant="outline" 
          className="h-11 px-5 rounded-2xl text-xs font-bold uppercase tracking-wider flex items-center gap-2 border-primary/30 text-primary hover:bg-primary/10 shadow-sm transition-all disabled:opacity-50"
        >
          {markAllReadMut.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCheck className="w-4 h-4" />
          )}
          <span>{markAllReadMut.isPending ? 'Marking All...' : 'Mark all as read'}</span>
        </Button>
      </div>

      <div className="flex flex-col gap-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-2 pb-2 overflow-x-auto">
          {[
            { id: 'all', label: 'All', icon: Bell, count: notifications.length },
            { id: 'unread', label: 'Unread', icon: CheckCircle2, count: unreadCount },
            { id: 'critical', label: 'Critical', icon: ShieldAlert },
            { id: 'warning', label: 'Warnings', icon: AlertTriangle },
            { id: 'info', label: 'Information', icon: MessageSquare }
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all border 
                ${filter === f.id ? 'bg-primary text-white border-primary shadow-lg shadow-primary/20' : 'bg-card border-border hover:border-primary/50 text-muted-foreground'}`}
            >
              <f.icon className="w-3.5 h-3.5" />
              <span>{f.label}</span>
              {typeof f.count === 'number' && f.count > 0 && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-extrabold ${filter === f.id ? 'bg-white/20 text-white' : 'bg-muted text-foreground'}`}>
                  {f.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input 
            placeholder="Search alerts by title or description..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-3 bg-card border border-border/60 rounded-2xl outline-none text-sm font-medium focus:border-primary/50 transition-all shadow-sm"
          />
        </div>

        {/* List */}
        <div className="flex flex-col gap-4">
          {isLoading && notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 bg-card rounded-3xl border border-border gap-3 animate-pulse">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
              <p className="text-sm font-semibold text-muted-foreground">Loading notifications...</p>
            </div>
          ) : (
            <AnimatePresence mode="popLayout">
              {filtered.map(n => (
                <NotificationCard 
                  key={n.id} 
                  notification={n} 
                  onRead={markRead}
                  onDelete={deleteNotification}
                  isMarking={activeActionId === n.id && markReadMut.isPending}
                  isDeleting={activeActionId === n.id && deleteNotifMut.isPending}
                />
              ))}
            </AnimatePresence>
          )}
          
          {!isLoading && filtered.length === 0 && (
            <div className="text-center py-20 bg-card rounded-3xl border border-dashed border-border">
              <div className="w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bell className="w-8 h-8 text-muted-foreground opacity-30" />
              </div>
              <h3 className="text-lg font-bold text-foreground">All Caught Up!</h3>
              <p className="text-sm text-muted-foreground mt-1">No notifications found in this category.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
