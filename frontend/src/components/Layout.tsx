import React, { useState, useEffect, useRef, useCallback } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import keycloak from '../keycloak';
import { LogOut, User, LayoutDashboard, Briefcase, Users, FileText, BarChart3, MessageSquare, ShieldCheck, Zap, Bell, Settings, Receipt } from 'lucide-react';
import { getUnreadCount, listNotifications, markAllRead, markNotificationRead, Notification } from '../utils/api';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const username = keycloak.tokenParsed?.preferred_username || 'User';
  const roles = keycloak.tokenParsed?.realm_access?.roles || [];

  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const canReceiveNotifications = roles.some(r => ['manager', 'hod', 'admin'].includes(r));

  const refreshUnread = useCallback(async () => {
    if (!canReceiveNotifications) return;
    setUnreadCount(await getUnreadCount());
  }, [canReceiveNotifications]);

  useEffect(() => {
    refreshUnread();
    const interval = setInterval(refreshUnread, 30000);
    return () => clearInterval(interval);
  }, [refreshUnread]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleBellClick = async () => {
    if (!showDropdown) {
      const notifs = await listNotifications();
      setNotifications(notifs);
    }
    setShowDropdown(prev => !prev);
  };

  const handleMarkAllRead = async () => {
    await markAllRead();
    setUnreadCount(0);
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
  };

  const handleNotifClick = async (n: Notification) => {
    if (!n.is_read) {
      await markNotificationRead(n.notification_id);
      setNotifications(prev => prev.map(x => x.notification_id === n.notification_id ? { ...x, is_read: true } : x));
      setUnreadCount(prev => Math.max(0, prev - 1));
    }
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };
  
  const navItems = [
    { label: 'Dashboard', icon: <LayoutDashboard size={18} />, path: '/dashboard', roles: ['candidate', 'recruiter', 'manager', 'hod', 'admin'] },
    { label: 'Job Requirements', icon: <Briefcase size={18} />, path: '/jobs', roles: ['recruiter', 'hod', 'admin'] },
    { label: 'Candidate Pool', icon: <Users size={18} />, path: '/candidates', roles: ['recruiter', 'admin'] },
    { label: 'Document Vault', icon: <FileText size={18} />, path: '/documents', roles: ['candidate', 'recruiter', 'hod', 'admin'] },
    { label: 'Communications', icon: <MessageSquare size={18} />, path: '/crm', roles: ['recruiter', 'manager', 'admin'] },
    { label: 'Matching Engine', icon: <Zap size={18} />, path: '/matching', roles: ['recruiter', 'manager', 'admin'] },
    { label: 'Form Responses', icon: <FileText size={18} />, path: '/form-responses', roles: ['recruiter', 'manager', 'admin'] },
    { label: 'Invoices', icon: <Receipt size={18} />, path: '/invoices', roles: ['manager', 'admin'] },
    { label: 'Analytics', icon: <BarChart3 size={18} />, path: '/analytics', roles: ['manager', 'admin', 'hod'] },
    { label: 'Configuration', icon: <Settings size={18} />, path: '/admin', roles: ['admin'] },
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
              onClick={() => keycloak.logout({ redirectUri: window.location.origin })}
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

            {canReceiveNotifications && (
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={handleBellClick}
                  className="relative p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors"
                  aria-label="Notifications"
                >
                  <Bell size={20} />
                  {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-[9px] font-bold text-white leading-none">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>

                {showDropdown && (
                  <div className="absolute right-0 top-12 w-96 bg-[#1e293b] border border-slate-700/60 rounded-2xl shadow-2xl z-50 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/60">
                      <span className="text-sm font-bold text-white">Notifications</span>
                      {unreadCount > 0 && (
                        <button
                          onClick={handleMarkAllRead}
                          className="text-[10px] font-bold text-blue-400 hover:text-blue-300 uppercase tracking-wider transition-colors"
                        >
                          Mark all read
                        </button>
                      )}
                    </div>

                    <div className="max-h-96 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="px-4 py-8 text-center text-slate-500 text-sm">No notifications</div>
                      ) : (
                        notifications.slice(0, 10).map(n => (
                          <div
                            key={n.notification_id}
                            onClick={() => handleNotifClick(n)}
                            className={`px-4 py-3 border-b border-slate-800/60 cursor-pointer transition-colors hover:bg-slate-800/40 ${!n.is_read ? 'bg-blue-900/10' : ''}`}
                          >
                            <div className="flex items-start gap-3">
                              {!n.is_read && (
                                <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-400" />
                              )}
                              <div className={!n.is_read ? '' : 'ml-5'}>
                                <p className={`text-sm font-semibold leading-tight ${n.is_read ? 'text-slate-400' : 'text-white'}`}>
                                  {n.title}
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5">{n.body}</p>
                                {n.data && (
                                  <div className="flex gap-2 mt-1.5">
                                    <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/15 text-blue-400 rounded font-medium">{n.data.pool_size} candidates</span>
                                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-700/50 text-slate-400 rounded font-medium">{n.data.jd_id}</span>
                                  </div>
                                )}
                                <p className="text-[10px] text-slate-600 mt-1">{formatTime(n.created_at)}</p>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
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
