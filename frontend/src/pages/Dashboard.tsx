import React, { useEffect, useState } from 'react';
import axios from 'axios';
import keycloak from '../keycloak';
import { Users, Globe, Activity, TrendingUp, Clock, CheckCircle2 } from 'lucide-react';

const Dashboard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const roles = keycloak.tokenParsed?.realm_access?.roles || [];
  
  const filteredRoles = roles.filter(r => 
    ['admin', 'manager', 'recruiter', 'hod', 'candidate', 'account_manager', 'senior_recruiter', 'junior_recruiter', 'intern'].includes(r)
  );

  const primaryRole = filteredRoles[0] || 'User';

  useEffect(() => {
    axios.get('http://localhost:8000/auth/me', {
      headers: {
        Authorization: `Bearer ${keycloak.token}`
      }
    })
    .then(response => setData(response.data))
    .catch(err => console.error("Error fetching auth data", err));
  }, []);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden bg-[#1e293b] border border-slate-700/50 rounded-3xl p-10 shadow-xl">
        <div className="relative z-10">
          <p className="text-blue-400 text-xs font-black uppercase tracking-[0.2em] mb-3">Enterprise Dashboard</p>
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            Welcome back, {keycloak.tokenParsed?.preferred_username}
          </h1>
          <div className="mt-5 flex flex-wrap gap-2">
            {filteredRoles.map(role => (
              <span key={role} className="px-3 py-1 bg-blue-500/10 text-blue-300 text-[10px] rounded-lg border border-blue-500/20 font-black uppercase tracking-wider">
                {role.replace('_', ' ')}
              </span>
            ))}
          </div>
        </div>
        <div className="absolute top-0 right-0 -mt-20 -mr-20 w-80 h-80 bg-blue-600/5 rounded-full blur-[80px]"></div>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard title="Total Candidates" value="1,248" icon={<Users size={24} />} trend="+12%" color="blue" />
        <StatCard title="Active JDs" value="42" icon={<Globe size={24} />} trend="+3" color="emerald" />
        <StatCard title="System Events" value="45.2k" icon={<Activity size={24} />} trend="+5.4k" color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Widget */}
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-8 shadow-sm">
          <h4 className="text-base font-bold text-white mb-6 flex items-center">
            <Clock size={18} className="mr-2 text-blue-400" />
            Recent Activity
          </h4>
          <div className="space-y-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-start space-x-4 border-l-2 border-slate-700 pl-4 ml-1">
                <div>
                  <p className="text-sm font-bold text-slate-200 uppercase tracking-tight">New Candidate Ingestion</p>
                  <p className="text-xs text-slate-500 mt-1 font-medium">Auto-matched to Senior Frontend Role • 1{i}m ago</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Status Widget */}
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-8 shadow-sm">
          <h4 className="text-base font-bold text-white mb-6 flex items-center">
            <CheckCircle2 size={18} className="mr-2 text-emerald-400" />
            Service Status
          </h4>
          <div className="grid gap-3">
            {['Matching Engine', 'Vector Search', 'Keycloak Auth'].map(service => (
              <div key={service} className="flex items-center justify-between p-4 bg-slate-900/40 rounded-2xl border border-slate-800/50">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">{service}</span>
                <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">Active</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const StatCard: React.FC<{ title: string; value: string; icon: React.ReactNode; trend?: string; color: string }> = ({ title, value, icon, trend, color }) => (
  <div className="bg-[#1e293b] border border-slate-700/50 p-7 rounded-3xl shadow-sm hover:border-slate-600 transition-all group">
    <div className="flex items-center justify-between mb-5">
      <div className={`p-3 rounded-2xl bg-slate-900 text-blue-400 border border-slate-700 group-hover:scale-110 transition-transform`}>
        {icon}
      </div>
      {trend && (
        <span className="text-[10px] font-black text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-lg border border-emerald-500/10">
          {trend}
        </span>
      )}
    </div>
    <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">{title}</p>
    <p className="text-3xl font-black text-white mt-1.5 tracking-tight">{value}</p>
  </div>
);

export default Dashboard;
