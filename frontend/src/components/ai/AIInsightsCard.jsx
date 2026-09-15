import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Sparkles,
  Lightbulb,
  Calendar,
  Clock,
  Flame,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  Info,
  ArrowRight,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

export const AIInsightsCard = ({
  riskData = null,
  insights = [],
  recommendations = [],
  isLoading = false,
  className = '',
}) => {
  const reasons = riskData?.reasons || [];
  const safeInsights = Array.isArray(insights) ? insights : [];
  const safeRecommendations = Array.isArray(recommendations) ? recommendations : [];

  const getInsightIcon = (type) => {
    switch (type) {
      case 'WEEKEND_PATTERN':
        return <Calendar className="w-4 h-4 text-amber-500" />;
      case 'TIMING_OPTIMIZATION':
        return <Clock className="w-4 h-4 text-blue-500" />;
      case 'STREAK_UPDATE':
        return <Flame className="w-4 h-4 text-orange-500" />;
      case 'RISK_WARNING':
        return <AlertTriangle className="w-4 h-4 text-destructive" />;
      case 'POSITIVE_REINFORCEMENT':
        return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
      default:
        return <Lightbulb className="w-4 h-4 text-primary" />;
    }
  };

  const getPriorityStyle = (priority) => {
    switch (priority) {
      case 'high':
        return 'bg-destructive/10 text-destructive border-destructive/20';
      case 'medium':
        return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
      case 'low':
      default:
        return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20';
    }
  };

  if (isLoading) {
    return (
      <Card className={`rounded-3xl border-border bg-card shadow-elevation-1 animate-pulse p-6 h-[360px] flex flex-col justify-center ${className}`}>
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

  const hasAnyData = reasons.length > 0 || safeInsights.length > 0 || safeRecommendations.length > 0;

  return (
    <Card className={`rounded-3xl border-border bg-card shadow-elevation-1 overflow-hidden h-[360px] flex flex-col ${className}`}>
      <CardHeader className="p-5 pb-3 border-b border-border/40 bg-gradient-to-r from-primary/5 via-accent/5 to-transparent shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-display font-bold text-base text-foreground flex items-center gap-1.5">
                AI Behavior & Adherence Insights
                <Sparkles className="w-3.5 h-3.5 text-accent fill-accent" />
              </h3>
              <p className="text-[11px] text-muted-foreground">
                ML-derived pattern detection and predictive feedback
              </p>
            </div>
          </div>
          {riskData?.model_version && (
            <Badge variant="outline" className="text-[10px] uppercase font-bold tracking-wider">
              v{riskData.model_version}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-5 space-y-5 overflow-y-auto flex-1">
        {/* Section 1: Explainable Risk Factors (SHAP reasons) */}
        {reasons.length > 0 && (
          <div className="space-y-2.5">
            <h4 className="text-xs font-black uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-primary" /> Key Risk Factors (What's driving this)
            </h4>
            <div className="grid gap-2">
              {reasons.map((reason, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-start gap-2.5 p-3 rounded-2xl bg-muted/40 border border-border/50 text-xs font-medium text-foreground"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span className="leading-snug">{reason}</span>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* Section 2: Behavioral Pattern Alerts */}
        {safeInsights.length > 0 && (
          <div className="space-y-2.5">
            <h4 className="text-xs font-black uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Detected Habit Patterns
            </h4>
            <div className="grid gap-2.5">
              {safeInsights.map((insight, idx) => (
                <div
                  key={insight.id || idx}
                  className="p-3.5 rounded-2xl border border-border/60 bg-card hover:bg-muted/20 transition-all flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {getInsightIcon(insight.type)}
                      <span className="font-bold text-xs text-foreground">{insight.title}</span>
                    </div>
                    {insight.priority && (
                      <span
                        className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full border ${getPriorityStyle(
                          insight.priority
                        )}`}
                      >
                        {insight.priority}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed pl-6">
                    {insight.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 3: Actionable Recommendations */}
        {safeRecommendations.length > 0 && (
          <div className="space-y-2.5">
            <h4 className="text-xs font-black uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Lightbulb className="w-3.5 h-3.5 text-primary" /> Personalized Next Steps
            </h4>
            <div className="grid gap-2">
              {safeRecommendations.map((rec, idx) => (
                <div
                  key={rec.id || idx}
                  className="p-3 rounded-2xl bg-primary/5 border border-primary/20 flex items-start gap-2.5 text-xs"
                >
                  <ArrowRight className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-foreground">{rec.title}</span>
                    <p className="text-muted-foreground text-[11px] mt-0.5">{rec.message}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Fallback if no specific patterns yet */}
        {!hasAnyData && (
          <div className="p-6 rounded-2xl bg-emerald-500/5 border border-emerald-500/20 text-center flex flex-col items-center gap-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500" />
            <h4 className="font-bold text-sm text-foreground">Optimal Adherence Recorded</h4>
            <p className="text-xs text-muted-foreground max-w-xs">
              No concerning non-adherence patterns detected in your recent dosing logs. Keep taking doses on schedule!
            </p>
          </div>
        )}

        {/* Upgrade note if present */}
        {riskData?.plan_note && (
          <div className="p-3 rounded-xl bg-accent/10 border border-accent/30 text-[11px] text-muted-foreground flex items-center justify-between">
            <span>{riskData.plan_note}</span>
          </div>
        )}

        {/* Advisory footer */}
        <p className="text-[10px] text-muted-foreground/60 text-center border-t border-border/40 pt-3">
          AI insights are advisory tools to assist with daily consistency. For any medical adjustments, consult your physician.
        </p>
      </CardContent>
    </Card>
  );
};
