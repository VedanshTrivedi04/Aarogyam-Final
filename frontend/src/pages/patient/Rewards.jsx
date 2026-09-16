import React from 'react';
import { motion } from 'framer-motion';
import { Trophy, Flame, Medal } from 'lucide-react';
import { useGamificationSummary, useBadges, useScores } from '@/hooks/useGamification';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { GamificationWidget } from '@/components/patient/GamificationWidget';

export default function Rewards() {
  const { data: summary } = useGamificationSummary();
  const { data: badgesData, isLoading: badgesLoading } = useBadges();
  const { data: scoresData, isLoading: scoresLoading } = useScores();

  // useBadges()/useScores() already resolve to the unwrapped array
  // (see AgentBase._call) — not a { data: [...] } wrapper.
  const badges = badgesData || [];
  const scores = scoresData || [];
  const streak = summary?.streak || {};

  return (
    <div className="flex flex-col gap-8 py-6 max-w-5xl mx-auto">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-display font-bold text-foreground">Your Rewards & Badges</h1>
        <p className="text-muted-foreground">Keep up your adherence to unlock exclusive badges and climb the ranks!</p>
      </div>

      {/* Top Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-1">
          <GamificationWidget />
        </div>
        <div className="md:col-span-2">
          <Card className="h-full border-border/50 bg-gradient-to-r from-background to-secondary/20">
            <CardContent className="p-6 flex flex-col justify-center h-full">
              <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Flame className="w-5 h-5 text-orange-500" />
                Streak Progress
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border border-border/50 bg-background flex gap-4 items-center">
                  <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center text-orange-500 shrink-0 text-xl font-bold">
                    {streak.current_days ?? 0}
                  </div>
                  <div>
                    <h4 className="font-bold text-sm">Current Streak</h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      {streak.current_days ? `${streak.current_days} day${streak.current_days === 1 ? '' : 's'} in a row` : 'Take a dose today to start a streak'}
                    </p>
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-border/50 bg-background flex gap-4 items-center">
                  <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center text-blue-500 shrink-0 text-xl font-bold">
                    {streak.longest_days ?? 0}
                  </div>
                  <div>
                    <h4 className="font-bold text-sm">Best Streak</h4>
                    <p className="text-xs text-muted-foreground mt-1">Your longest streak so far</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Badges Section */}
      <div className="flex flex-col gap-4 mt-4">
        <h2 className="text-2xl font-display font-bold flex items-center gap-2">
          <Medal className="w-6 h-6 text-primary" />
          Unlocked Badges
        </h2>
        {badgesLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 animate-pulse">
            {[1, 2, 3, 4].map(i => (
              <Card key={i} className="h-40 bg-muted/50 border-0" />
            ))}
          </div>
        ) : badges.length === 0 ? (
          <div className="p-8 text-center bg-card rounded-2xl border border-dashed border-border/60">
            <Trophy className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <h3 className="font-bold text-lg mb-1">No badges yet</h3>
            <p className="text-muted-foreground text-sm">Keep tracking your medication to earn your first badge!</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {badges.map((badge, idx) => (
              <motion.div
                key={badge.id || idx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card className="h-full border-border/40 hover:border-primary/40 transition-colors hover:shadow-md cursor-pointer group text-center">
                  <CardContent className="p-5 flex flex-col items-center gap-3">
                    <div className="w-16 h-16 rounded-full bg-gradient-to-br from-yellow-100 to-yellow-200 border border-yellow-300 flex items-center justify-center group-hover:scale-110 transition-transform shadow-inner text-3xl">
                      {badge.icon || '🏅'}
                    </div>
                    <div>
                      <h4 className="font-bold text-sm leading-tight text-foreground">{badge.name}</h4>
                      <p className="text-[10px] text-muted-foreground mt-1 line-clamp-2">{badge.description}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Leaderboard / History */}
      <div className="flex flex-col gap-4 mt-6">
        <h2 className="text-2xl font-display font-bold flex items-center gap-2">
          <Trophy className="w-6 h-6 text-primary" />
          Weekly Performance
        </h2>
        <Card>
          <CardContent className="p-0">
            {scoresLoading ? (
              <div className="p-6 text-center text-muted-foreground">Loading scores...</div>
            ) : scores.length === 0 ? (
               <div className="p-6 text-center text-muted-foreground">No scores recorded yet.</div>
            ) : (
              <div className="divide-y divide-border">
                {scores.map((score, idx) => (
                  <div key={score.id || idx} className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-secondary text-primary flex items-center justify-center font-bold">
                        #{idx + 1}
                      </div>
                      <div>
                        <h4 className="font-bold text-sm">Week of {new Date(score.week_start).toLocaleDateString()}</h4>
                        <p className="text-xs text-muted-foreground">Completed {score.taken_doses} / {score.total_doses} doses</p>
                      </div>
                    </div>
                    <Badge variant="primary" className="text-sm px-3 py-1">
                      {score.score}%
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

    </div>
  );
}
