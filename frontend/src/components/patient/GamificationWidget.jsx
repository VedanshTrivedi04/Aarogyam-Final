import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Trophy, ChevronRight, Zap } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useGamificationSummary } from '@/hooks/useGamification';

export function GamificationWidget() {
  const { data: summary, isLoading } = useGamificationSummary();

  if (isLoading) {
    return (
      <Card className="animate-pulse bg-card/50">
        <CardContent className="p-6 h-32" />
      </Card>
    );
  }

  // useGamificationSummary() already resolves to the unwrapped API payload
  // (see AgentBase._call) — it's { streak, recent_badges, recent_scores }, not
  // a points/level system (that concept doesn't exist on the backend).
  const streak       = summary?.streak || {};
  const currentDays  = streak.current_days ?? 0;
  const longestDays  = streak.longest_days ?? 0;
  const badgeCount   = summary?.recent_badges?.length ?? 0;
  const latestBadge  = summary?.recent_badges?.[0];
  const progress     = longestDays > 0 ? Math.min(100, (currentDays / longestDays) * 100) : (currentDays > 0 ? 100 : 0);

  return (
    <Card className="bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 text-white overflow-hidden relative shadow-lg group">
      {/* Decorative background elements */}
      <div className="absolute -right-6 -top-6 w-32 h-32 bg-white/10 rounded-full blur-2xl" />
      <div className="absolute -left-6 -bottom-6 w-32 h-32 bg-white/10 rounded-full blur-2xl" />

      <CardContent className="p-6 relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-300 fill-yellow-300" />
            <h3 className="font-display font-bold text-lg">{currentDays} Day Streak</h3>
          </div>
          <Badge variant="secondary" className="bg-white/20 hover:bg-white/30 text-white border-0 backdrop-blur-md">
            {badgeCount} badge{badgeCount === 1 ? '' : 's'}
          </Badge>
        </div>

        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-xs font-medium mb-1.5 opacity-90">
              <span>Best streak: {longestDays} day{longestDays === 1 ? '' : 's'}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-2 bg-black/20 rounded-full overflow-hidden backdrop-blur-sm">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 1, delay: 0.2 }}
                className="h-full bg-white rounded-full"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2 bg-black/20 px-3 py-1.5 rounded-lg backdrop-blur-sm">
              <Trophy className="w-4 h-4 text-yellow-300" />
              <span className="text-sm font-bold">
                {latestBadge ? `${latestBadge.icon} ${latestBadge.name}` : 'No badges yet'}
              </span>
            </div>

            <Link to="/patient/rewards" className="flex items-center text-sm font-medium hover:text-yellow-200 transition-colors">
              View Badges <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
