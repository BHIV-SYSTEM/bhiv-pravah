'use client';

import React, { useEffect, useState } from 'react';
import { useLiveDashboard, useAppRegistry, useObserverStatus } from '../hooks/useBackend';
import { Server, Activity, RefreshCw } from 'lucide-react';

export default function StatusBar() {
  const [time, setTime] = useState<string>('');
  
  const dashboard = useLiveDashboard();
  const controlPlane = useAppRegistry();
  const observer = useObserverStatus();

  useEffect(() => {
    const tick = () => {
      setTime(new Date().toLocaleTimeString());
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const dbConnected = dashboard.isSuccess;
  const cpConnected = controlPlane.isSuccess;
  const obsConnected = observer.isSuccess;

  // Track if any active polling is happening
  const isFetching = dashboard.isFetching || controlPlane.isFetching || observer.isFetching;

  return (
    <footer className="h-11 border-t border-border bg-card text-xs text-muted-foreground flex items-center justify-between px-4 select-none z-50 shrink-0 font-mono">
      {/* Left side: Services health */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Server className="w-3.5 h-3.5" />
          <span>Decision Brain:</span>
          <div className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${dbConnected ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-rose-500 shadow-[0_0_6px_#ef4444]'}`} />
            <span className={dbConnected ? 'text-emerald-500 font-semibold' : 'text-rose-500'}>
              {dbConnected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <Server className="w-3.5 h-3.5" />
          <span>Control Plane:</span>
          <div className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${cpConnected ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-rose-500 shadow-[0_0_6px_#ef4444]'}`} />
            <span className={cpConnected ? 'text-emerald-500 font-semibold' : 'text-rose-500'}>
              {cpConnected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <Server className="w-3.5 h-3.5" />
          <span>Observer:</span>
          <div className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${obsConnected ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-rose-500 shadow-[0_0_6px_#ef4444]'}`} />
            <span className={obsConnected ? 'text-emerald-500 font-semibold' : 'text-rose-500'}>
              {obsConnected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* Right side: Sync state & Time */}
      <div className="flex items-center gap-4">
        {isFetching && (
          <div className="flex items-center gap-1 text-primary">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>SYNCING...</span>
          </div>
        )}

        <div className="flex items-center gap-1">
          <Activity className="w-3.5 h-3.5" />
          <span>STABILITY SCORE:</span>
          <span className="text-foreground font-semibold">
            {dashboard.data?.error_analytics?.statistics?.test_coverage_avg 
              ? `${100 - (dashboard.data.error_analytics.statistics.critical_issues * 15)}%` 
              : '98%'}
          </span>
        </div>

        <div className="border-l border-border pl-4">
          <span>{time}</span>
        </div>
      </div>
    </footer>
  );
}
