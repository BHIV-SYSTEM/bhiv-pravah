'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useUiStore } from '../store/useUiStore';
import { usePostOverride } from '../hooks/useBackend';
import { Search, Compass, Terminal, Shield, RefreshCw, Sun, Moon, Sliders, PlaySquare } from 'lucide-react';
import { toast } from 'sonner';

export default function CommandPalette() {
  const router = useRouter();
  const { commandPaletteOpen, setCommandPaletteOpen, addNotification } = useUiStore();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  
  const postOverride = usePostOverride();

  // Listen for Cmd/Ctrl + K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      } else if (e.key === 'Escape') {
        setCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  // Focus input when opened
  useEffect(() => {
    if (commandPaletteOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelectedIndex(0);
    }
  }, [commandPaletteOpen]);

  const items = [
    // Page Jumps
    { category: 'Navigation', title: 'Go to Dashboard', icon: Compass, action: () => router.push('/') },
    { category: 'Navigation', title: 'Go to Control Plane', icon: Sliders, action: () => router.push('/control-plane') },
    { category: 'Navigation', title: 'Go to Runtime Controller', icon: PlaySquare, action: () => router.push('/runtime') },
    { category: 'Navigation', title: 'Go to Telemetry & Events', icon: Terminal, action: () => router.push('/telemetry') },
    { category: 'Navigation', title: 'Go to Observer Server', icon: Shield, action: () => router.push('/observer') },
    { category: 'Navigation', title: 'Go to Replay Center', icon: RefreshCw, action: () => router.push('/replay') },
    
    // Command overrides
    { 
      category: 'System Governance', 
      title: 'Trigger Override: Freeze AI-CRM service', 
      icon: Shield, 
      action: () => {
        postOverride.mutate({ app_name: 'ai-crm', action: 'freeze', duration: 300, reason: 'Manual operator override' });
        toast.info('Sending manual freeze request for AI-CRM');
        addNotification('Operator initiated manual freeze override on AI-CRM.', 'warn');
      } 
    },
    { 
      category: 'System Governance', 
      title: 'Trigger Override: Clear AI-CRM Freeze', 
      icon: Shield, 
      action: () => {
        postOverride.mutate({ app_name: 'ai-crm', action: 'clear_freeze' });
        toast.success('Clearing freeze override on AI-CRM');
        addNotification('Operator cleared manual freeze override on AI-CRM.', 'info');
      } 
    },
    
    // Theme triggers
    { 
      category: 'Preferences', 
      title: 'Switch to Dark Mode', 
      icon: Moon, 
      action: () => {
        document.documentElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
        toast.success('Theme updated to Dark Mode');
      }
    },
    { 
      category: 'Preferences', 
      title: 'Switch to Light Mode', 
      icon: Sun, 
      action: () => {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
        toast.success('Theme updated to Light Mode');
      }
    },
  ];

  // Filter items
  const filtered = items.filter(item => 
    item.title.toLowerCase().includes(query.toLowerCase()) || 
    item.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % filtered.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + filtered.length) % filtered.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action();
        setCommandPaletteOpen(false);
      }
    }
  };

  if (!commandPaletteOpen) return null;

  return (
    <div 
      ref={overlayRef}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center pt-24 px-4 select-none transition-all duration-200"
      onClick={(e) => { if (e.target === overlayRef.current) setCommandPaletteOpen(false); }}
    >
      <div 
        className="w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[420px] transition-all transform scale-100"
        onKeyDown={handleKeyDown}
      >
        {/* Search header */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-3 bg-secondary/30">
          <Search className="w-4.5 h-4.5 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command or page path..."
            className="w-full bg-transparent border-0 outline-0 focus:ring-0 text-foreground text-sm font-sans placeholder-muted-foreground"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
          />
          <span className="text-[10px] text-muted-foreground bg-secondary border border-border px-1.5 py-0.5 rounded font-mono shrink-0">ESC</span>
        </div>

        {/* List items */}
        <div className="overflow-y-auto flex-1 py-2 divide-y divide-border/20">
          {filtered.length > 0 ? (
            filtered.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={idx}
                  className={`flex items-center justify-between px-4 py-2.5 cursor-pointer text-xs transition-colors duration-150 ${isSelected ? 'bg-primary/10 text-primary border-l-2 border-primary font-medium' : 'text-foreground hover:bg-secondary/40'}`}
                  onClick={() => { item.action(); setCommandPaletteOpen(false); }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4.5 h-4.5 shrink-0 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                    <span>{item.title}</span>
                  </div>
                  <span className={`text-[10px] font-mono select-none px-1.5 py-0.5 rounded ${isSelected ? 'text-primary bg-primary/15' : 'text-muted-foreground bg-secondary/80 border border-border/40'}`}>
                    {item.category}
                  </span>
                </div>
              );
            })
          ) : (
            <div className="text-center py-8 text-xs text-muted-foreground">
              No matching commands or pages found.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
