import { useSuperAdminGamification } from '@/hooks/useSuperAdmin';
import { Card, CardContent } from '@/components/ui/Card';
import { Trophy, Flame, Award, TrendingUp } from 'lucide-react';

export default function SuperAdminGamification() {
  const { data, isLoading } = useSuperAdminGamification();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const summary = data?.summary || {};

  const statCards = [
    { title: 'Active Streaks', value: summary.total_streaks || 0, icon: Flame, color: 'text-orange-600', bgColor: 'bg-orange-50' },
    { title: 'Badges Earned', value: summary.total_badges_earned || 0, icon: Award, color: 'text-accent-600', bgColor: 'bg-accent-500/10' },
    { title: 'Longest Streak Ever', value: `${summary.longest_streak_ever || 0}d`, icon: Trophy, color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <Trophy className="w-6 h-6 mr-2 text-accent-500" />
          Gamification & Rewards
        </h1>
        <p className="text-slate-500 mt-1">Platform-wide streaks, badges, and weekly adherence engagement.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {statCards.map((stat, idx) => (
          <Card key={idx} className="border-slate-200/60 shadow-sm">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">{stat.title}</p>
                  <h3 className="text-3xl font-bold text-slate-900">{stat.value}</h3>
                </div>
                <div className={`p-3 rounded-xl ${stat.bgColor}`}>
                  <stat.icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
              <Flame className="w-5 h-5 mr-2 text-orange-500" />
              Top Streaks
            </h2>
            <div className="space-y-3">
              {data?.top_streaks?.map((s, idx) => (
                <div key={idx} className="flex justify-between items-center text-sm border-b border-slate-50 pb-2">
                  <span className="font-medium text-slate-900">{s.patient}</span>
                  <span className="text-orange-600 font-semibold">{s.current_days}d current / {s.longest_days}d best</span>
                </div>
              ))}
              {(!data?.top_streaks || data.top_streaks.length === 0) && (
                <p className="text-center text-slate-400 py-6">No active streaks yet.</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/60 shadow-sm">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4">Badge Distribution</h2>
            <div className="space-y-2">
              {data?.badge_distribution?.map((b, idx) => (
                <div key={idx} className="flex justify-between text-sm">
                  <span className="text-slate-600">{b.badge_type.replace(/_/g, ' ')}</span>
                  <span className="font-semibold text-slate-900">{b.count}</span>
                </div>
              ))}
              {(!data?.badge_distribution || data.badge_distribution.length === 0) && (
                <p className="text-center text-slate-400 py-6">No badges earned yet.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200/60 shadow-sm">
        <CardContent className="p-6">
          <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
            <TrendingUp className="w-5 h-5 mr-2 text-accent-500" />
            Weekly Adherence Engagement
          </h2>
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="text-slate-500 border-b border-slate-100">
              <tr>
                <th className="py-2">Week Of</th>
                <th className="py-2">Avg Score</th>
                <th className="py-2 text-right">Patients Scored</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.weekly_trend?.map((w, idx) => (
                <tr key={idx}>
                  <td className="py-2">{new Date(w.week_start).toLocaleDateString()}</td>
                  <td className="py-2">{Math.round(w.avg_score)}%</td>
                  <td className="py-2 text-right font-medium">{w.patients}</td>
                </tr>
              ))}
              {(!data?.weekly_trend || data.weekly_trend.length === 0) && (
                <tr><td colSpan="3" className="py-6 text-center text-slate-400">No weekly scores yet.</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
