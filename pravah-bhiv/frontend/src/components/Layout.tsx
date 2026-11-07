'use client';
 
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useUiStore } from '../store/useUiStore';
import StatusBar from './StatusBar';
import CommandPalette from './CommandPalette';
import NotificationCenter from './NotificationCenter';
import { 
  Compass, 
  Sliders, 
  PlaySquare, 
  Terminal, 
  Shield, 
  RefreshCw, 
  Activity, 
  Code, 
  Settings, 
  FileText, 
  BarChart3,
  Menu,
  X,
  Bell,
  Sun,
  Moon,
  Search,
  User,
  ChevronRight,
  Sparkles,
  Leaf
} from 'lucide-react';

interface SidebarItem {
  name: string;
  href: string;
  icon: React.ComponentType<any>;
  badge?: string | number;
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { sidebarOpen, toggleSidebar, notifications, toggleCommandPalette } = useUiStore();
  const [notifOpen, setNotifOpen] = useState(false);
  const [darkTheme, setDarkTheme] = useState(true);

  // Sync initial theme
  useEffect(() => {
    const isDark = localStorage.getItem('theme') !== 'light';
    setDarkTheme(isDark);
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const toggleTheme = () => {
    const nextDark = !darkTheme;
    setDarkTheme(nextDark);
    if (nextDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  };

  const navItems: SidebarItem[] = [
    { name: 'Dashboard', href: '/', icon: Compass },
    { name: 'Control Plane', href: '/control-plane', icon: Sliders },
    { name: 'VANA Control Center', href: '/vana', icon: Leaf },
    { name: 'Runtime', href: '/runtime', icon: PlaySquare },
    { name: 'Telemetry', href: '/telemetry', icon: Terminal },
    { name: 'Observer', href: '/observer', icon: Shield },
    { name: 'Replay Engine', href: '/replay', icon: RefreshCw },
    { name: 'Services', href: '/services', icon: Activity },
    { name: 'API Explorer', href: '/api-explorer', icon: Code },
    { name: 'Live Logs', href: '/logs', icon: FileText },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Configuration', href: '/configuration', icon: Settings },
  ];

  const unreadNotifs = notifications.filter(n => !n.read).length;

  // Resolve Breadcrumbs from Path
  const getBreadcrumbs = () => {
    if (pathname === '/') return [{ label: 'Pravah Console', href: '/', active: true }];
    const parts = pathname.split('/').filter(Boolean);
    return [
      { label: 'Pravah Console', href: '/', active: false },
      ...parts.map((part, idx) => ({
        label: part.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
        href: '/' + parts.slice(0, idx + 1).join('/'),
        active: idx === parts.length - 1
      }))
    ];
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background text-foreground transition-colors duration-200">
      
      {/* Top Navbar */}
      <header className="h-16 border-b border-border bg-card flex items-center justify-between px-5 shrink-0 select-none z-40">
        <div className="flex items-center gap-3">
          <button 
            onClick={toggleSidebar} 
            className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors md:flex hidden"
          >
            <Menu className="w-5 h-5" />
          </button>
          
          {/* Logo */}
          <div className="flex items-center gap-2 mr-4">
            <div className="bg-primary p-1.5 rounded-lg text-primary-foreground shadow-[0_0_12px_rgba(99,102,241,0.4)]">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-extrabold tracking-tight font-sans text-base linear-text">
              PRAVAH
            </span>
          </div>

          {/* Breadcrumb Navigation */}
          <nav className="md:flex items-center gap-1.5 text-sm text-muted-foreground hidden font-mono">
            {breadcrumbs.map((crumb, idx) => (
              <React.Fragment key={idx}>
                {idx > 0 && <ChevronRight className="w-3.5 h-3.5" />}
                {crumb.active ? (
                  <span className="text-foreground font-semibold">{crumb.label}</span>
                ) : (
                  <Link href={crumb.href || '/'} className="hover:text-foreground transition-colors">
                    {crumb.label}
                  </Link>
                )}
              </React.Fragment>
            ))}
          </nav>
        </div>

        {/* Header Right Tools */}
        <div className="flex items-center gap-2">
          {/* Cmd+K Search trigger */}
          <button 
            onClick={toggleCommandPalette}
            className="flex items-center gap-3 px-5 py-2.5 text-sm text-muted-foreground bg-secondary/80 hover:bg-secondary border border-border rounded-xl transition-colors font-mono select-none"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="md:inline hidden">Search console...</span>
            <span className="text-[10px] bg-card px-1.5 py-0.5 rounded border border-border">Ctrl+K</span>
          </button>

          {/* Theme switcher */}
          <button 
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            title="Toggle theme"
          >
            {darkTheme ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          {/* Notification dropdown trigger */}
          <div className="relative">
            <button 
              onClick={() => setNotifOpen(!notifOpen)}
              className={`p-2 rounded-lg hover:bg-secondary transition-colors relative ${notifOpen ? 'bg-secondary text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Bell className="w-4 h-4" />
              {unreadNotifs > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-primary ring-2 ring-card animate-pulse" />
              )}
            </button>
            <NotificationCenter isOpen={notifOpen} onClose={() => setNotifOpen(false)} />
          </div>

          <div className="border-l border-border h-6 mx-1" />

          {/* User Menu placeholder */}
          <button className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors">
            <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs font-bold">
              <User className="w-3.5 h-3.5" />
            </div>
            <span className="text-xs font-medium md:inline hidden">Operator</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Sidebar */}
        <aside 
          className={`border-r border-border bg-card shrink-0 select-none z-30 transition-all duration-300 flex flex-col justify-between ${sidebarOpen ? 'w-60' : 'w-0 -translate-x-full md:w-16 md:translate-x-0'}`}
        >
          {/* Main Links */}
          <div className="py-4 px-3 overflow-y-auto flex-1 flex flex-col gap-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link 
                  key={item.name} 
                  href={item.href}
                  className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm transition-all duration-150 group ${isActive ? 'bg-primary/10 text-primary font-semibold shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]' : 'text-muted-foreground hover:bg-secondary/40 hover:text-foreground'}`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 group-hover:scale-105 transition-transform ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                    <span className={sidebarOpen ? 'inline' : 'md:hidden inline'}>{item.name}</span>
                  </div>
                  {item.badge && sidebarOpen && (
                    <span className="bg-primary/25 text-primary text-[10px] px-1.5 py-0.5 rounded font-bold font-mono">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>

          {/* Sidebar bottom indicator */}
          {sidebarOpen && (
            <div className="p-4 border-t border-border/60 bg-secondary/15 flex flex-col gap-1 text-[10px] text-muted-foreground font-mono">
              <span className="text-foreground/75 font-semibold">TANTRA CONSTITUTION</span>
              <span>Guardrails: ENFORCED</span>
              <span>Auditing: CONTINUOUS</span>
            </div>
          )}
        </aside>

        {/* Main Workspace content */}
        <main className="flex-1 overflow-y-auto p-6 bg-background relative flex flex-col">
          {children}
        </main>
      </div>

      {/* Command Palette */}
      <CommandPalette />

      {/* Status Bar */}
      <StatusBar />
    </div>
  );
}
