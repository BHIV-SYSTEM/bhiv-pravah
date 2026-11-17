'use client';

import React from 'react';
import { useUiStore } from '../store/useUiStore';
import { Bell, CheckCircle2, AlertTriangle, AlertCircle, Info, Trash2, Check } from 'lucide-react';

export default function NotificationCenter({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const { notifications, markAllNotificationsRead, clearNotifications } = useUiStore();

  if (!isOpen) return null;

  const unreadCount = notifications.filter(n => !n.read).length;

  const getIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
      case 'warn': return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-rose-500" />;
      default: return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  const getBg = (type: string) => {
    switch (type) {
      case 'success': return 'bg-emerald-500/10 border-emerald-500/20';
      case 'warn': return 'bg-amber-500/10 border-amber-500/20';
      case 'error': return 'bg-rose-500/10 border-rose-500/20';
      default: return 'bg-blue-500/10 border-blue-500/20';
    }
  };

  const formatTimeAgo = (isoString: string): string => {
    try {
      const diffMs = Date.now() - new Date(isoString).getTime();
      const diffSecs = Math.floor(diffMs / 1000);
      const diffMins = Math.floor(diffSecs / 60);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffSecs < 10) return 'just now';
      if (diffSecs < 60) return `${diffSecs}s ago`;
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return `${diffDays}d ago`;
    } catch {
      return 'some time ago';
    }
  };

  return (
    <div className="absolute right-0 mt-2 w-80 bg-card border border-border rounded-xl shadow-2xl overflow-hidden z-50 flex flex-col font-mono text-xs select-none">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-secondary/30">
        <div className="flex items-center gap-1.5 font-sans font-semibold">
          <Bell className="w-4 h-4 text-foreground" />
          <span>Alert Feed</span>
          {unreadCount > 0 && (
            <span className="bg-primary text-primary-foreground text-[9px] font-bold px-1.5 py-0.5 rounded-full">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {unreadCount > 0 && (
            <button 
              onClick={() => markAllNotificationsRead()}
              className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded hover:bg-secondary"
              title="Mark all read"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
          )}
          {notifications.length > 0 && (
            <button 
              onClick={() => clearNotifications()}
              className="text-muted-foreground hover:text-rose-500 transition-colors p-1 rounded hover:bg-secondary"
              title="Clear all"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="max-h-[300px] overflow-y-auto divide-y divide-border/40 py-1">
        {notifications.length > 0 ? (
          notifications.map((notif) => (
            <div 
              key={notif.id}
              className={`p-3 transition-colors duration-150 flex gap-2.5 items-start ${notif.read ? 'opacity-70 bg-card' : 'bg-primary/5'}`}
            >
              <div className={`p-1.5 rounded-lg border ${getBg(notif.type)} shrink-0`}>
                {getIcon(notif.type)}
              </div>
              <div className="flex-1 flex flex-col gap-1">
                <span className="text-foreground font-sans leading-relaxed">{notif.message}</span>
                <span className="text-[9px] text-muted-foreground font-mono">
                  {formatTimeAgo(notif.timestamp)}
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-12 text-muted-foreground font-sans">
            No alerts or system events in feed.
          </div>
        )}
      </div>
    </div>
  );
}
