import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import keycloak from '../keycloak';
import { LogOut, User, LayoutDashboard, Briefcase, Users, FileText, BarChart3, MessageSquare, ShieldCheck, Zap } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const username = keycloak.tokenParsed?.preferred_username || 'User';
  const roles = keycloak.tokenParsed?.realm_access?.roles || [];
  
  const navItems = [
    { label: 'Dashboard', icon: <LayoutDashboard size={18} />, path: '/dashboard', roles: ['candidate', 'recruiter', 'manager', 'hod', 'admin'] },
    { label: 'Job Requirements', icon: <Briefcase size={18} />, path: '/jobs', roles: ['recruiter', 'manager', 'hod', 'admin'] },
    { label: 'Candidate Pool', icon: <Users size={18} />, path: '/candidates', roles: ['recruiter', 'manager', 'admin'] },
    { label: 'Document Vault', icon: <FileText size={18} />, path: '/documents', roles: ['recruiter', 'manager', 'hod', 'admin'] },
    { label: 'Communications', icon: <MessageSquare size={18} />, path: '/crm', roles: ['recruiter', 'manager', 'admin'] },
    { label: 'Matching Engine', icon: <Zap size={18} />, path: '/matching', roles: ['recruiter', 'manager', 'admin'] },
    { label: 'Analytics', icon: <BarChart3 size={18} />, path: '/analytics', roles: ['manager', 'admin', 'hod'] },
  ];

  const filteredNav = navItems.filter(item => 
    item.roles.some(role => roles.includes(role))
  );

  const getPageTitle = () => {
     const currentItem = navItems.find(item => location.pathname === item.path);
     return currentItem ? currentItem.label : 'Dashboard';
  };

  const mainRole = roles.find(r => ['admin', 'manager', 'recruiter', 'hod', 'candidate'].includes(r)) || 'User';

  return (
    <div className="flex h-screen w-screen bg-[#0f172a] text-slate-100 overflow-hidden">
      {/* Sidebar - Darker Background */}
      <aside className="w-72 bg-[#020617] border-r border-slate-800/80 flex flex-col shrink-0 z-20">
        <div className="p-8">
          <div className="flex items-center space-x-3">
            <div className="bg-blue-600 p-2 rounded-xl">
              <ShieldCheck className="text-white" size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white leading-none tracking-tight">JobOS</h1>
              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Enterprise</p>
            </div>
          </div>
        </div>
        
        <nav className="flex-1 px-4 space-y-1.5 overflow-y-auto mt-4">
          {filteredNav.map((item) => (
            <NavLink
              key={item.label}
              to={item.path}
              className={({ isActive }) => 
                `flex items-center space-x-3 px-4 py-3 rounded-xl transition-all ${
                  isActive 
                    ? 'bg-blue-600 text-white shadow-lg' 
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                }`
              }
            >
              <span>{item.icon}</span>
              <span className="font-semibold text-sm">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-6">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-4">
            <div className="flex items-center space-x-3 mb-4">
              <div className="bg-slate-700 p-2 rounded-lg">
                <User className="text-slate-300" size={20} />
              </div>
              <div className="overflow-hidden">
                <p className="text-sm font-bold truncate text-white uppercase tracking-tight">{username}</p>
                <p className="text-[10px] text-blue-400 font-bold uppercase">{mainRole}</p>
              </div>
            </div>
            <button
              onClick={() => keycloak.logout()}
              className="w-full py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-bold rounded-xl border border-red-500/10 transition-colors flex items-center justify-center space-x-2"
            >
              <LogOut size={14} />
              <span>Log Out</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content - Deep Navy Background */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <header className="h-20 border-b border-slate-800/80 flex items-center justify-between px-10 bg-[#0f172a]/80 backdrop-blur-md shrink-0">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">{getPageTitle()}</h2>
            <p className="text-xs text-slate-400 font-medium mt-0.5">Recruitment Operating System v2.0</p>
          </div>
          <div className="flex items-center space-x-4">
             <div className="flex items-center space-x-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-500"></div>
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">System Online</span>
             </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-y-auto p-10 custom-scrollbar">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Layout;
