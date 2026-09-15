import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Bell, 
  Search, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldAlert,
  MoreVertical,
  MessageSquare
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from '@/hooks/useNotifications';

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


const NotificationCard = ({ notification, onRead }) => {
  const getIcon = () => {
    switch (notification.category) {
      case 'critical': return <ShieldAlert className="w-5 h-5 text-destructive" />;
      case 'warning': return <AlertTriangle className="w-5 h-5 text-accent" />;
      case 'info': return <Bell className="w-5 h-5 text-primary" />;
      default: return <CheckCircle2 className="w-5 h-5 text-success" />;
    }
  };

  const getBg = () => {
    if (!notification.unread) return 'bg-card';
    switch (notification.category) {
      case 'critical': return 'bg-destructive/5 border-destructive/20';
      case 'warning': return 'bg-accent/5 border-accent/20';
      default: return 'bg-primary/5 border-primary/20';
    }
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-5 rounded-2xl border transition-all group ${getBg()} ${!notification.unread ? 'border-border/50 hover:border-primary/30' : ''}`}
    >
      <div className="flex gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 
          ${notification.unread ? 'bg-white shadow-sm' : 'bg-muted/50 text-muted-foreground'}`}>
          {getIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <h4 className={`font-bold text-sm truncate ${notification.unread ? 'text-foreground' : 'text-muted-foreground'}`}>
              {notification.title}
            </h4>
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider shrink-0">{notification.time}</span>
          </div>
          <p className={`text-sm leading-relaxed mb-3 ${notification.unread ? 'text-foreground/80' : 'text-muted-foreground'}`}>
            {notification.message}
          </p>
          
          <div className="flex items-center justify-between">
            {notification.action && (
              <Button variant={notification.category === 'critical' ? 'danger' : 'secondary'} size="sm" className="h-8 px-4 text-[10px] font-black uppercase tracking-widest rounded-lg">
                {notification.action}
              </Button>
            )}
            <div className="flex gap-1">
              {notification.unread && (
                <button onClick={() => onRead(notification.id)} className="p-2 rounded-lg hover:bg-black/5 text-muted-foreground transition-colors" title="Mark as read">
                  <CheckCircle2 className="w-4 h-4" />
                </button>
              )}
              <button className="p-2 rounded-lg hover:bg-black/5 text-muted-foreground transition-colors">
                <MoreVertical className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default function NotificationsCentre() {
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: { results: apiNotifications = [], unreadCount: apiUnreadCount } = {}, isLoading } = useNotifications();
  const markReadMut = useMarkNotificationRead();
  const markAllReadMut = useMarkAllNotificationsRead();

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
    markReadMut.mutate(id);
  };

  const markAllRead = () => {
    markAllReadMut.mutate();
  };

  const filtered = notifications.filter(n => {
    if (searchQuery && !n.title.toLowerCase().includes(searchQuery.toLowerCase()) && !n.message.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (filter === 'all') return true;
    if (filter === 'unread') return n.unread;
    return n.category === filter;
  });

  const unreadCount = apiUnreadCount || notifications.filter(n => n.unread).length;

  return (
    <div className="flex flex-col gap-8 py-4 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-3xl font-display font-bold text-foreground tracking-tight">Notifications</h2>
            {unreadCount > 0 && (
              <Badge variant="primary" className="h-6 px-2">{unreadCount} New</Badge>
            )}
          </div>
          <p className="text-muted-foreground font-medium">Stay updated with your clinical alerts and device status.</p>
        </div>
        <Button onClick={markAllRead} variant="outline" className="h-10 rounded-xl text-xs font-bold uppercase tracking-wider">
          Mark all as read
        </Button>
      </div>

      <div className="flex flex-col gap-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-2 pb-2 overflow-x-auto">
          {[
            { id: 'all', label: 'All', icon: Bell },
            { id: 'unread', label: 'Unread', icon: CheckCircle2 },
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
              {f.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input 
            placeholder="Search alerts by medicine or patient name..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-3 bg-card border border-border/60 rounded-2xl outline-none text-sm font-medium focus:border-primary/50 transition-all"
          />
        </div>

        {/* List */}
        <div className="flex flex-col gap-4">
          <AnimatePresence mode="popLayout">
            {filtered.map(n => (
              <NotificationCard key={n.id} notification={n} onRead={markRead} />
            ))}
          </AnimatePresence>
          
          {filtered.length === 0 && (
            <div className="text-center py-20 bg-card rounded-3xl border border-dashed border-border">
              <div className="w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bell className="w-8 h-8 text-muted-foreground opacity-30" />
              </div>
              <h3 className="text-lg font-bold text-foreground">All Caught Up!</h3>
              <p className="text-sm text-muted-foreground mt-1">No notifications found in this category.</p>
            </div>
          )}
        </div>

        {filtered.length > 0 && (
          <Button variant="ghost" className="w-full h-12 text-muted-foreground hover:text-primary font-bold text-sm">
            Load Older Notifications
          </Button>
        )}
      </div>
    </div>
  );
}
