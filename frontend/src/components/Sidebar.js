import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, Building2, Zap } from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: Upload, label: 'Upload Deck' },
  { to: '/companies', icon: Building2, label: 'Companies' },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="w-[220px] min-h-screen bg-surface border-r border-border flex flex-col" data-testid="sidebar">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-sm bg-primary flex items-center justify-center">
            <Zap size={18} className="text-white" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-sm text-text-primary tracking-tight">DealSense</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest">VC Intelligence</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => {
          const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));
          return (
            <NavLink
              key={to}
              to={to}
              data-testid={`nav-${label.toLowerCase().replace(' ', '-')}`}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-sm text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-primary/10 text-primary border-l-2 border-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-hl'
              }`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="text-[10px] text-text-muted uppercase tracking-widest">Powered by AI</div>
        <div className="text-xs text-text-secondary mt-1">GPT-4o + Multi-Source</div>
      </div>
    </aside>
  );
}
