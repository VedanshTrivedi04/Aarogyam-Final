import React from 'react';
import { motion, useTransform, useMotionValue, animate } from 'framer-motion';
import { AlertTriangle, Activity, Sparkles, Info, ShieldCheck } from 'lucide-react';

export const RiskMeter = ({
  riskScore = null,
  riskLevel = null,
  confidence = null,
  source = null,
  planNote = null,
  isLoading = false,
  compact = false,
}) => {
  // SVG Arc constants
  const radius = 80;
  const strokeWidth = 12;
  const circumference = Math.PI * radius; // Half-circle

  // Normalize score: 0.0 - 1.0 becomes 0 - 100
  const normalizedScore = React.useMemo(() => {
    if (typeof riskScore === 'number' && !Number.isNaN(riskScore)) {
      return riskScore <= 1.0 && riskScore > 0 ? Math.round(riskScore * 100) : Math.min(100, Math.max(0, Math.round(riskScore)));
    }
    if (riskLevel) {
      const map = { low: 20, medium: 50, high: 78, critical: 92 };
      return map[riskLevel.toLowerCase()] ?? 25;
    }
    return 0;
  }, [riskScore, riskLevel]);

  const levelStr = (riskLevel || (normalizedScore >= 70 ? 'high' : normalizedScore >= 35 ? 'medium' : 'low')).toLowerCase();

  // Motion value for smooth needle / arc animation
  const scoreAnim = useMotionValue(0);

  React.useEffect(() => {
    const controls = animate(scoreAnim, normalizedScore, {
      duration: 1.4,
      ease: [0.175, 0.885, 0.32, 1.275],
    });
    return () => controls.stop();
  }, [normalizedScore, scoreAnim]);

  // Color interpolation based on normalized score (0-100)
  const color = useTransform(
    scoreAnim,
    [0, 30, 65, 85, 100],
    ['#10b981', '#10b981', '#f59e0b', '#f97316', '#ef4444']
  );

  const strokeDashoffset = useTransform(
    scoreAnim,
    [0, 100],
    [circumference, 0]
  );

  const levelBadges = {
    low: { bg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20', label: 'Low Risk', icon: ShieldCheck },
    medium: { bg: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20', label: 'Medium Risk', icon: Info },
    high: { bg: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20', label: 'High Risk', icon: AlertTriangle },
    critical: { bg: 'bg-destructive/10 text-destructive border-destructive/30 animate-pulse', label: 'Critical Risk', icon: AlertTriangle },
  };

  const badge = levelBadges[levelStr] || levelBadges.low;
  const BadgeIcon = badge.icon;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-6 bg-card rounded-3xl border border-border animate-pulse min-h-[220px]">
        <Activity className="w-8 h-8 text-muted-foreground/40 animate-spin mb-3" />
        <p className="text-xs font-semibold text-muted-foreground">Evaluating AI Risk Model...</p>
      </div>
    );
  }

  return (
    <div className={`flex flex-col items-center justify-center bg-card rounded-3xl border border-border shadow-elevation-1 transition-all ${compact ? 'p-4' : 'p-6'}`}>
      {/* Header */}
      <div className="flex w-full justify-between items-center mb-4">
        <h3 className="font-display font-bold text-sm md:text-base flex items-center text-foreground gap-2">
          <Sparkles className="w-4 h-4 text-primary shrink-0" />
          <span>AI Adherence Risk</span>
        </h3>
        <span className={`inline-flex items-center text-[11px] font-black uppercase tracking-wider px-2.5 py-1 rounded-full border ${badge.bg}`}>
          <BadgeIcon className="w-3 h-3 mr-1" />
          {badge.label}
        </span>
      </div>

      {/* Gauge Container */}
      <div className="relative w-48 h-24 overflow-hidden my-2">
        {/* Background Arc */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 200 100">
          <path
            d="M 20 90 A 80 80 0 0 1 180 90"
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            className="text-muted/40"
          />
          {/* Active Arc */}
          <motion.path
            d="M 20 90 A 80 80 0 0 1 180 90"
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            style={{ strokeDashoffset }}
          />
        </svg>

        {/* Value display */}
        <div className="absolute bottom-0 left-0 right-0 flex flex-col items-center">
          <motion.span
            className="font-mono text-4xl font-extrabold tracking-tighter"
            style={{ color }}
          >
            {riskScore !== null ? Math.round(normalizedScore) : (levelStr.toUpperCase())}
          </motion.span>
          <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-black">
            {riskScore !== null ? 'Risk Score (0–100)' : 'Assessed Level'}
          </span>
        </div>
      </div>

      {/* Meta tags & provenance */}
      <div className="flex flex-wrap items-center justify-center gap-2 mt-3 text-[11px]">
        {source && (
          <span className="px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-semibold">
            {source === 'ML_MODEL' ? '🧠 XGBoost Engine' : '⚙️ Rule-Based'}
          </span>
        )}
        {confidence !== null && confidence !== undefined && (
          <span className="px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-semibold">
            {Math.round(confidence * 100)}% Confidence
          </span>
        )}
      </div>

      {/* Plan upgrade notice if free tier */}
      {planNote && (
        <p className="text-[11px] text-muted-foreground/80 text-center mt-2 px-2 italic">
          {planNote}
        </p>
      )}

      {/* Advisory disclaimer */}
      <p className="text-[10px] text-muted-foreground/60 text-center mt-3 border-t border-border/40 pt-2 w-full">
        Advisory only · Non-clinical prediction
      </p>
    </div>
  );
};

