// Premium Glass Layout Component
import React, { useEffect, useRef, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  ChartBarIcon,
  ListBulletIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '@/hooks/useAuth';
import { apiService } from '@/services/api';

const Layout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [budget, setBudget] = useState<any>(null);

  // Last balance the data provider reported. Shown because a run that cannot
  // be paid for is now refused, and the user deserves to see why beforehand.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const load = async () => {
      try {
        const res = await apiService.getProviderUsage();
        if (!cancelled && res.success) setBudget(res.data?.scrapecreators || null);
      } catch {
        /* meter is informational; never block the UI on it */
      }
    };
    load();
    const timer = setInterval(load, 60000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [user, location.pathname]);

  const isActive = (path: string) => location.pathname === path;

  // Close the profile menu on outside clicks
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const initials = user
    ? (user.first_name?.[0] || user.username?.[0] || user.email?.[0] || 'U').toUpperCase()
    : 'U';

  return (
    <div className="min-h-screen relative overflow-hidden font-sans text-white">
      {/* Ambient background glow effects */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-500/20 rounded-full blur-[120px] animate-pulse-slow" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-secondary-500/20 rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
      </div>

      {/* Floating Glass Navigation */}
      <nav className="fixed top-4 left-1/2 -translate-x-1/2 w-[95%] max-w-7xl z-50 transition-all duration-300">
        <div className="glass-panel rounded-2xl px-6 py-3 flex items-center justify-between">

          {/* Logo Area */}
          <div className="flex items-center space-x-3 cursor-pointer group" onClick={() => navigate('/')}>
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-tr from-primary-500 to-secondary-500 rounded-full blur opacity-75 group-hover:opacity-100 transition duration-1000"></div>
              <img
                src="/logo.png"
                alt="Vanta Logo"
                className="relative h-10 w-10 rounded-full object-cover border border-white/10 group-hover:scale-105 transition-transform duration-300 shadow-lg"
              />
            </div>
            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70 tracking-tight font-display">
              Vanta
            </span>
          </div>

          {/* Navigation Links */}
          <div className="hidden md:flex items-center space-x-1 bg-black/20 rounded-xl p-1 border border-white/5">
            <button
              onClick={() => navigate('/dashboard')}
              className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${isActive('/dashboard') || isActive('/')
                ? 'bg-primary-500/20 text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] border border-primary-500/30'
                : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <ChartBarIcon className="h-4 w-4 mr-2" />
              Dashboard
            </button>
            <button
              onClick={() => navigate('/tasks')}
              className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${isActive('/tasks')
                ? 'bg-primary-500/20 text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] border border-primary-500/30'
                : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <ListBulletIcon className="h-4 w-4 mr-2" />
              Tasks
            </button>
          </div>

          {/* Right Actions */}
          <div className="flex items-center space-x-4">
            <div className="h-8 w-[1px] bg-white/10 hidden sm:block"></div>
            <div className="flex items-center space-x-3">
              <div className="px-3 py-1.5 rounded-full bg-primary-500/10 border border-primary-500/20 flex items-center space-x-2">
                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-[0_0_10px_#4ade80]" />
                <span className="text-xs font-medium text-primary-200">System Online</span>
              </div>
              {budget && budget.known && (
                <div
                  title={`${budget.message}${budget.observed_at ? ` Last observed ${budget.observed_at}.` : ''}`}
                  className={`hidden sm:flex px-3 py-1.5 rounded-full border items-center space-x-2 ${
                    budget.enough
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-200'
                      : 'bg-rose-500/10 border-rose-500/25 text-rose-200'
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-current opacity-70" />
                  <span className="text-xs font-medium">
                    {budget.remaining} credits · ~{budget.runs_left} {budget.runs_left === 1 ? 'run' : 'runs'} left
                  </span>
                </div>
              )}
              {/* Profile menu */}
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen((v) => !v)}
                  className="flex items-center space-x-2 rounded-full bg-black/20 border border-white/10 pl-1 pr-2 py-1 hover:bg-white/10 transition-colors"
                  aria-label="Profile menu"
                >
                  <span className="h-8 w-8 rounded-full bg-gradient-to-tr from-primary-500 to-secondary-500 flex items-center justify-center text-sm font-bold text-white">
                    {initials}
                  </span>
                  <ChevronDownIcon className={`h-4 w-4 text-white/60 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
                </button>
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-64 glass-panel rounded-xl p-2 shadow-2xl">
                    <div className="px-3 py-2 border-b border-white/10">
                      <div className="text-sm font-semibold text-white truncate">
                        {user?.first_name || user?.username || 'Account'}
                      </div>
                      <div className="text-xs text-white/60 truncate">{user?.email}</div>
                    </div>
                    <button
                      onClick={() => { setMenuOpen(false); navigate('/settings'); }}
                      className="mt-1 w-full flex items-center px-3 py-2 rounded-lg text-sm text-white/80 hover:bg-white/10 hover:text-white transition-colors"
                    >
                      <Cog6ToothIcon className="h-4 w-4 mr-2" />
                      Settings
                    </button>
                    <button
                      onClick={() => { setMenuOpen(false); logout(); window.location.href = '/login'; }}
                      className="w-full flex items-center px-3 py-2 rounded-lg text-sm text-red-300 hover:bg-red-500/10 hover:text-red-200 transition-colors"
                    >
                      <ArrowRightOnRectangleIcon className="h-4 w-4 mr-2" />
                      Log out
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="pt-28 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto min-h-screen relative z-0">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;