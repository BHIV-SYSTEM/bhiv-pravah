'use client';

import React, { useState } from 'react';
import { 
  useLiveDashboard, 
  useHealthOverview, 
  usePostOverride,
  useActionScope
} from '../../hooks/useBackend';
import { 
  Sliders, 
  ShieldAlert, 
  Play, 
  Flame, 
  Plus, 
  ShieldCheck, 
  Shield,
  Settings, 
  Activity, 
  XOctagon, 
  RefreshCw,
  Loader2
} from 'lucide-react';
import { toast } from 'sonner';

export default function ControlPlane() {
  const { data: dashboard, isLoading: dashLoading } = useLiveDashboard();
  const { data: healthOverview, isLoading: healthLoading, refetch: refetchHealth } = useHealthOverview();
  const { data: actionScope } = useActionScope();
  
  const postOverride = usePostOverride();

  // Selected app override form
  const [selectedApp, setSelectedApp] = useState('');
  const [overrideAction, setOverrideAction] = useState<'freeze' | 'clear_freeze'>('freeze');
  const [duration, setDuration] = useState(300);
  const [reason, setReason] = useState('Operator troubleshooting');

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedApp) {
      toast.error('Please select an app');
      return;
    }

    toast.promise(
      postOverride.mutateAsync({
        app_name: selectedApp,
        action: overrideAction,
        duration: overrideAction === 'freeze' ? duration : undefined,
        reason: overrideAction === 'freeze' ? reason : undefined
      }),
      {
        loading: 'Sending override request to Control Plane...',
        success: () => {
          setSelectedApp('');
          refetchHealth();
          return `Successfully applied override for ${selectedApp.toUpperCase()}`;
        },
        error: (err) => err.message || 'Override action failed'
      }
    );
  };

  const isLoading = dashLoading || healthLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING CONTROL PLANE STATE...</span>
      </div>
    );
  }

  const getAppStatus = (app: any): { label: string; pillClass: string; isFrozen: boolean } => {
    const isFrozen = app.manual_freeze === true || app.freeze === true || app.status === 'frozen';
    if (isFrozen) {
      return { label: 'FROZEN', pillClass: 'critical', isFrozen: true };
    }
    const rawStatus = (app.status || '').toLowerCase();
    if (rawStatus === 'healthy' || rawStatus === 'online') {
      return { label: 'ONLINE', pillClass: 'healthy', isFrozen: false };
    }
    if (rawStatus === 'unreachable' || rawStatus === 'offline' || rawStatus === 'error') {
      return { label: 'OFFLINE', pillClass: 'critical', isFrozen: false };
    }
    if (rawStatus === 'degraded') {
      return { label: 'DEGRADED', pillClass: 'degraded', isFrozen: false };
    }
    if (rawStatus === 'unknown' || !app.status) {
      // Control Plane has app registered in spec, but runtime health check has not reported telemetry
      return { label: 'STATUS NOT REPORTED', pillClass: 'info', isFrozen: false };
    }
    return { label: String(app.status).toUpperCase(), pillClass: 'info', isFrozen: false };
  };

  // Fetch active apps directly from backend registry
  const activeApps = healthOverview?.overview || [];

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Sliders className="w-5 h-5 text-primary" />
            Control Plane
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Orchestrate active agents, govern action scopes, and view real-time overrides
          </p>
        </div>
      </header>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Managed Agents / Apps */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4">
          <div className="flex justify-between items-center border-b border-border/40 pb-2">
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Orchestrated System Registry</span>
            <button 
              onClick={() => refetchHealth()}
              className="p-1 hover:text-primary transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {activeApps.length > 0 ? (
              activeApps.map((app: any, idx: number) => {
                const name = app.app_name || app.name || app.id || `Agent-${idx}`;
                const { label: statusLabel, pillClass, isFrozen } = getAppStatus(app);
                return (
                  <div key={idx} className="border border-border rounded-lg p-4 bg-secondary/20 flex flex-col gap-3 relative overflow-hidden group">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-extrabold text-foreground uppercase tracking-wide truncate flex-1 min-w-0" title={name}>{name}</span>
                      <span className={`status-pill ${pillClass} shrink-0`}>
                        {statusLabel}
                      </span>
                    </div>

                    <div className="flex flex-col gap-1 text-[10px] text-muted-foreground">
                      <div>Source: <span className="text-foreground">{app.source_type || 'unknown'}</span> ({app.runtime || 'system'})</div>
                      {app.health_endpoint && (
                        <div>Health Probe: <span className="font-mono text-foreground">{app.health_endpoint}</span></div>
                      )}
                      {app.last_action && <div>Last Action: <span className="text-primary font-bold uppercase">{app.last_action}</span></div>}
                      {app.last_seen && <div>Last Seen: <span className="text-foreground">{new Date(app.last_seen).toLocaleTimeString()}</span></div>}
                    </div>

                    {/* Icon indicator */}
                    <div className="absolute right-3 bottom-3 opacity-10 group-hover:opacity-20 transition-opacity">
                      {isFrozen ? (
                        <XOctagon className="w-12 h-12 text-rose-500" />
                      ) : statusLabel === 'ONLINE' ? (
                        <ShieldCheck className="w-12 h-12 text-emerald-500" />
                      ) : (
                        <Shield className="w-12 h-12 text-blue-400" />
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="col-span-full py-8 text-center text-muted-foreground italic">
                No active compute services registered.
              </div>
            )}
          </div>
        </div>

        {/* Override Control Console */}
        <div className="premium-card flex flex-col gap-4">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2 flex items-center gap-1.5 text-rose-500">
            <ShieldAlert className="w-4 h-4" />
            Override Operator
          </span>

          <form onSubmit={handleOverrideSubmit} className="flex flex-col gap-4 mt-2">
            {/* Select App */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-muted-foreground uppercase">Target Application:</label>
              <select 
                className="bg-secondary/40 text-foreground border border-border rounded-lg px-3 py-2 outline-none font-mono focus:border-primary w-full text-xs"
                value={selectedApp}
                onChange={(e) => setSelectedApp(e.target.value)}
              >
                <option value="">Select App...</option>
                 {activeApps.map((app: any, idx: number) => {
                   const n = app.app_name || app.name || app.id || `agent-${idx}`;
                   return <option key={idx} value={n}>{n.toUpperCase()}</option>;
                 })}
              </select>
            </div>

            {/* Override Action */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-muted-foreground uppercase">Action Type:</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setOverrideAction('freeze')}
                  className={`py-2.5 px-4 rounded-xl font-bold border transition-all text-xs cursor-pointer active:scale-98 ${overrideAction === 'freeze' ? 'bg-rose-500/10 text-rose-500 border-rose-500 shadow-sm' : 'bg-transparent text-muted-foreground border-border hover:text-foreground'}`}
                >
                  FREEZE
                </button>
                <button
                  type="button"
                  onClick={() => setOverrideAction('clear_freeze')}
                  className={`py-2.5 px-4 rounded-xl font-bold border transition-all text-xs cursor-pointer active:scale-98 ${overrideAction === 'clear_freeze' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500 shadow-sm' : 'bg-transparent text-muted-foreground border-border hover:text-foreground'}`}
                >
                  ACTIVATE / UNFREEZE
                </button>
              </div>
            </div>

            {/* Duration (if freeze) */}
            {overrideAction === 'freeze' && (
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] text-muted-foreground uppercase">Freeze Duration (seconds):</label>
                <input 
                  type="number" 
                  min={10} 
                  max={36000}
                  className="bg-secondary/40 text-foreground border border-border rounded-xl px-4 py-2.5 outline-none font-mono focus:border-primary text-xs shadow-inner"
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                />
              </div>
            )}

            {/* Reason */}
            {overrideAction === 'freeze' && (
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] text-muted-foreground uppercase">Justification / Reason:</label>
                <textarea 
                  className="bg-secondary/40 text-foreground border border-border rounded-xl px-4 py-2.5 outline-none font-mono focus:border-primary text-xs h-20 resize-none shadow-inner"
                  placeholder="Troubleshooting database lock latency spikes..."
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
            )}

            <button 
              type="submit"
              disabled={postOverride.isPending}
              className="mt-2 w-full py-3 px-5 rounded-xl bg-primary text-primary-foreground hover:opacity-90 font-sans font-extrabold uppercase tracking-wider text-center flex items-center justify-center gap-2 text-xs transition-all active:scale-[0.98] shadow-md border border-primary/20 cursor-pointer"
            >
              <Activity className="w-4 h-4" />
              COMMIT OVERRIDE TO PLANE
            </button>
          </form>
        </div>

      </div>

      {/* Allowed Action Scope Matrix */}
      <section className="premium-card flex flex-col gap-4 mt-2">
        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">
          Constitutional Action Scope Policies
        </span>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 leading-relaxed">
          {actionScope ? (
            Object.entries(actionScope).map(([env, actions]) => (
              <div key={env} className="flex flex-col gap-2 p-3 bg-secondary/15 border border-border/40 rounded-lg">
                <span className="font-bold text-foreground capitalize border-b border-border/40 pb-1">{env} Environment</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {actions.map((act, i) => (
                    <span key={i} className="bg-secondary border border-border text-muted-foreground text-[9px] px-2 py-0.5 rounded font-mono uppercase">
                      {act}
                    </span>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <div className="text-muted-foreground italic text-xs">No active scope policies ingested.</div>
          )}
        </div>
      </section>

    </div>
  );
}
