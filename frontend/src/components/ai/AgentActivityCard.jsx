import React from 'react';
import { motion } from 'framer-motion';
import {
  Bot,
  Sparkles,
  Bell,
  BellRing,
  Users,
  Stethoscope,
  CheckCircle2,
  XCircle,
  Clock,
  History,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const TOOL_META = {
  send_notification: { icon: Bell, label: 'Sent a gentle reminder' },
  send_reminder: { icon: BellRing, label: 'Sent a reminder' },
  request_caregiver_alert: { icon: Users, label: 'Alerted your caregiver' },
  create_doctor_review: { icon: Stethoscope, label: 'Flagged for doctor review' },
};

const STATUS_BADGE = {
  EXECUTED: { variant: 'success', label: 'Sent' },
  FAILED: { variant: 'danger', label: 'Failed' },
  SKIPPED: { variant: 'default', label: 'Skipped' },
  PENDING_APPROVAL: { variant: 'warning', label: 'Pending Approval' },
};

const timeAgo = (isoString) => {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

export const AgentActivityCard = ({ activity = [], isLoading = false }) => {
  const safeActivity = Array.isArray(activity) ? activity : [];

  if (isLoading) {
    return (
      <Card className="rounded-3xl border-border bg-card shadow-elevation-1 animate-pulse p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-xl bg-muted" />
          <div className="h-4 w-40 bg-muted rounded" />
        </div>
        <div className="space-y-3">
          <div className="h-14 bg-muted/60 rounded-2xl" />
          <div className="h-14 bg-muted/60 rounded-2xl" />
        </div>
      </Card>
    );
  }

  return (
    <Card className="rounded-3xl border-border bg-card shadow-elevation-1 overflow-hidden">
      <CardHeader className="p-6 pb-4 border-b border-border/40 bg-gradient-to-r from-primary/5 via-accent/5 to-transparent">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-display font-bold text-base text-foreground flex items-center gap-1.5">
              AI Agent Activity
              <Sparkles className="w-3.5 h-3.5 text-accent fill-accent" />
            </h3>
            <p className="text-[11px] text-muted-foreground">
              What the AI Agent has done to help with adherence
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 space-y-2.5">
        {safeActivity.length === 0 ? (
          <div className="p-6 rounded-2xl bg-muted/30 border border-border/50 text-center flex flex-col items-center gap-2">
            <History className="w-8 h-8 text-muted-foreground/60" />
            <h4 className="font-bold text-sm text-foreground">No AI Actions Yet</h4>
            <p className="text-xs text-muted-foreground max-w-xs">
              The AI Agent steps in automatically when your adherence risk rises — nothing to show yet.
            </p>
          </div>
        ) : (
          <div className="grid gap-2.5">
            {safeActivity.map((item, idx) => {
              const meta = TOOL_META[item.tool_name] || { icon: Bell, label: item.tool_name };
              const Icon = meta.icon;
              const statusBadge = STATUS_BADGE[item.status] || { variant: 'default', label: item.status };
              const hasOutcome = item.outcome && item.outcome.success !== null && item.outcome.success !== undefined;

              return (
                <motion.div
                  key={item.id || idx}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="p-3.5 rounded-2xl border border-border/60 bg-card hover:bg-muted/20 transition-all flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4 text-primary shrink-0" />
                      <span className="font-bold text-xs text-foreground">{meta.label}</span>
                    </div>
                    <Badge variant={statusBadge.variant} className="text-[9px] uppercase font-black tracking-widest">
                      {statusBadge.label}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1.5 pl-6 text-[11px] text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    {timeAgo(item.created_at)}
                  </div>
                  {hasOutcome && (
                    <div className="pl-6 flex items-center gap-1.5 text-[11px]">
                      {item.outcome.success ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                          <span className="text-emerald-600 dark:text-emerald-400 font-medium">Worked — dose was taken</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5 text-destructive shrink-0" />
                          <span className="text-destructive font-medium">Didn't help — dose still missed</span>
                        </>
                      )}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}

        <p className="text-[10px] text-muted-foreground/60 text-center border-t border-border/40 pt-3 mt-1">
          The AI Agent's actions are advisory and automated based on your adherence risk. It never changes your medications or dosage.
        </p>
      </CardContent>
    </Card>
  );
};
