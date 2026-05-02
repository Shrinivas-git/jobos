import React, { useState, useEffect } from 'react';
import { BarChart2, Users, Clock, AlertTriangle, TrendingUp, CheckCircle2 } from 'lucide-react';
import keycloak from '../keycloak';
import {
  getPipelineHealth, getRecruiterPerformance, getTimeToFill,
  PipelineHealth, RecruiterPerf, TimeToFill,
} from '../utils/api';

const ALLOWED_ROLES = ['admin', 'manager', 'hod'];

const STAGE_COLORS: Record<string, string> = {
  shortlist: 'bg-blue-500',
  interview: 'bg-violet-500',
  offer: 'bg-amber-500',
  joined: 'bg-emerald-500',
};

const STAGE_TEXT: Record<string, string> = {
  shortlist: 'text-blue-400',
  interview: 'text-violet-400',
  offer: 'text-amber-400',
  joined: 'text-emerald-400',
};

const Analytics: React.FC = () => {
  const roles: string[] = keycloak.tokenParsed?.realm_access?.roles || [];
  const hasAccess = roles.some(r => ALLOWED_ROLES.includes(r));

  const [health, setHealth] = useState<PipelineHealth | null>(null);
  const [recruiters, setRecruiters] = useState<RecruiterPerf[]>([]);
  const [ttf, setTtf] = useState<TimeToFill | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasAccess) { setLoading(false); return; }
    Promise.all([getPipelineHealth(), getRecruiterPerformance(), getTimeToFill()])
      .then(([h, r, t]) => {
        setHealth(h);
        setRecruiters(r);
        setTtf(t);
        setLoading(false);
      });
  }, [hasAccess]);

  if (!hasAccess) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        Access restricted to managers and administrators.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
        Loading analytics...
      </div>
    );
  }

  const maxReached = health ? Math.max(...health.funnel.map(f => f.reached_count), 1) : 1;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      {/* Header */}
      <div className="relative overflow-hidden bg-[#1e293b] border border-slate-700/50 rounded-3xl p-10 shadow-xl">
        <div className="relative z-10">
          <p className="text-blue-400 text-xs font-black uppercase tracking-[0.2em] mb-3">Analytics</p>
          <h1 className="text-4xl font-extrabold text-white tracking-tight">Pipeline Intelligence</h1>
          <p className="text-slate-400 text-sm mt-2">Pipeline health, recruiter performance, and time-to-fill.</p>
        </div>
        <div className="absolute top-0 right-0 -mt-20 -mr-20 w-80 h-80 bg-blue-600/5 rounded-full blur-[80px]" />
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <KpiCard
          title="Active Candidates"
          value={health ? String(health.total_active) : '—'}
          sub="in pipeline"
          icon={<Users size={24} />}
          color="blue"
        />
        <KpiCard
          title="SLA Breaches"
          value={health ? String(health.sla_breach_total) : '—'}
          sub="need attention"
          icon={<AlertTriangle size={24} />}
          color={health && health.sla_breach_total > 0 ? 'red' : 'emerald'}
        />
        <KpiCard
          title="Avg Time-to-Fill"
          value={ttf?.summary.avg_days != null ? `${ttf.summary.avg_days}d` : '—'}
          sub={ttf ? `${ttf.summary.filled_count} positions filled` : 'no fills yet'}
          icon={<Clock size={24} />}
          color="amber"
        />
      </div>

      {/* Pipeline Funnel */}
      {health && (
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-8 shadow-sm">
          <h4 className="text-base font-bold text-white mb-6 flex items-center gap-2">
            <TrendingUp size={18} className="text-blue-400" />
            Pipeline Funnel
            <span className="ml-1 text-xs text-slate-500 font-normal">{health.total_active} active</span>
          </h4>
          <div className="space-y-6">
            {health.funnel.map((stage, i) => (
              <div key={stage.stage}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-black uppercase tracking-widest ${STAGE_TEXT[stage.stage] || 'text-slate-400'}`}>
                      {stage.stage}
                    </span>
                    {stage.breach_count > 0 && (
                      <span className="text-[9px] font-black text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full border border-red-500/20">
                        {stage.breach_count} breach{stage.breach_count !== 1 ? 'es' : ''}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-5 text-right">
                    <span className="text-xs text-slate-500">{stage.reached_count} ever reached</span>
                    <span className="text-sm font-bold text-white w-8 text-right">{stage.current_count}</span>
                    <span className="text-[10px] font-black text-slate-500 w-12 text-right">{stage.conversion_pct}%</span>
                  </div>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${STAGE_COLORS[stage.stage] || 'bg-slate-500'}`}
                    style={{ width: `${maxReached > 0 ? (stage.reached_count / maxReached) * 100 : 0}%` }}
                  />
                </div>
                {i < health.funnel.length - 1
                  && stage.reached_count > 0
                  && health.funnel[i + 1].reached_count > 0 && (
                  <div className="text-[10px] text-slate-600 mt-1 text-right">
                    {Math.round(health.funnel[i + 1].reached_count / stage.reached_count * 100)}% advance to {health.funnel[i + 1].stage}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recruiter Performance */}
      {recruiters.length > 0 && (
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-8 shadow-sm">
          <h4 className="text-base font-bold text-white mb-6 flex items-center gap-2">
            <CheckCircle2 size={18} className="text-emerald-400" />
            Recruiter Performance
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-black text-slate-500 uppercase tracking-widest border-b border-slate-800">
                  <th className="pb-3 text-left">Recruiter</th>
                  <th className="pb-3 text-right">Tasks</th>
                  <th className="pb-3 text-right">Done</th>
                  <th className="pb-3 text-right">Overdue</th>
                  <th className="pb-3 text-right">Avg Days</th>
                  <th className="pb-3 text-right">Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {recruiters.map(r => (
                  <tr key={r.recruiter_id} className="hover:bg-slate-800/20 transition-colors">
                    <td className="py-3.5 text-slate-200 font-medium">{r.recruiter_name}</td>
                    <td className="py-3.5 text-right text-slate-400">{r.total_tasks}</td>
                    <td className="py-3.5 text-right text-emerald-400 font-bold">{r.completed_tasks}</td>
                    <td className="py-3.5 text-right">
                      <span className={r.overdue_tasks > 0 ? 'text-red-400 font-bold' : 'text-slate-500'}>
                        {r.overdue_tasks}
                      </span>
                    </td>
                    <td className="py-3.5 text-right text-slate-400">
                      {r.avg_days_to_complete != null ? `${r.avg_days_to_complete}d` : '—'}
                    </td>
                    <td className="py-3.5 text-right">
                      <span className={`text-xs font-black px-2 py-1 rounded-lg ${
                        r.completion_rate >= 80
                          ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                          : r.completion_rate >= 50
                          ? 'text-amber-400 bg-amber-500/10 border border-amber-500/20'
                          : 'text-red-400 bg-red-500/10 border border-red-500/20'
                      }`}>
                        {r.completion_rate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Time-to-Fill */}
      {ttf && (
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-8 shadow-sm">
          <div className="flex items-start justify-between mb-6">
            <h4 className="text-base font-bold text-white flex items-center gap-2">
              <Clock size={18} className="text-amber-400" />
              Time-to-Fill by Position
            </h4>
            {ttf.summary.filled_count > 0 && (
              <div className="flex gap-6 text-right">
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest font-black">Min</p>
                  <p className="text-xl font-black text-white">{ttf.summary.min_days}d</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest font-black">Avg</p>
                  <p className="text-xl font-black text-amber-400">{ttf.summary.avg_days}d</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest font-black">Max</p>
                  <p className="text-xl font-black text-white">{ttf.summary.max_days}d</p>
                </div>
              </div>
            )}
          </div>
          {ttf.jds.length === 0 ? (
            <p className="text-slate-500 text-sm">No positions found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] font-black text-slate-500 uppercase tracking-widest border-b border-slate-800">
                    <th className="pb-3 text-left">Position</th>
                    <th className="pb-3 text-left">Status</th>
                    <th className="pb-3 text-right">Opened</th>
                    <th className="pb-3 text-right">Filled</th>
                    <th className="pb-3 text-right">Days</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {ttf.jds.map(jd => (
                    <tr key={jd.jd_id} className="hover:bg-slate-800/20 transition-colors">
                      <td className="py-3.5 text-slate-200 font-medium max-w-xs truncate pr-4">{jd.title}</td>
                      <td className="py-3.5">
                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-1 rounded-full ${
                          jd.status === 'active'
                            ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                            : 'text-slate-500 bg-slate-800 border border-slate-700'
                        }`}>
                          {jd.status || 'unknown'}
                        </span>
                      </td>
                      <td className="py-3.5 text-right text-slate-500 text-xs">
                        {jd.created_at ? new Date(jd.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3.5 text-right text-slate-500 text-xs">
                        {jd.filled_at ? new Date(jd.filled_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3.5 text-right">
                        {jd.days_to_fill != null ? (
                          <span className={`text-sm font-bold ${
                            jd.days_to_fill <= 30 ? 'text-emerald-400'
                            : jd.days_to_fill <= 60 ? 'text-amber-400'
                            : 'text-red-400'
                          }`}>
                            {jd.days_to_fill}d
                          </span>
                        ) : (
                          <span className="text-slate-600 text-xs italic">open</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!health && recruiters.length === 0 && !ttf && (
        <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
          No analytics data available yet.
        </div>
      )}
    </div>
  );
};

const KpiCard: React.FC<{
  title: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
  color: string;
}> = ({ title, value, sub, icon, color }) => {
  const textColor: Record<string, string> = {
    blue: 'text-blue-400',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
  };
  return (
    <div className="bg-[#1e293b] border border-slate-700/50 p-7 rounded-3xl shadow-sm hover:border-slate-600 transition-all group">
      <div className="flex items-center justify-between mb-5">
        <div className="p-3 rounded-2xl bg-slate-900 border border-slate-700 group-hover:scale-110 transition-transform">
          <span className={textColor[color] || 'text-blue-400'}>{icon}</span>
        </div>
      </div>
      <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">{title}</p>
      <p className={`text-3xl font-black mt-1.5 tracking-tight ${textColor[color] || 'text-white'}`}>{value}</p>
      <p className="text-slate-600 text-xs mt-1">{sub}</p>
    </div>
  );
};

export default Analytics;
