'use client';

import React from 'react';
import { useLiveDashboard, useAutonomousStatus } from '../../hooks/useBackend';
import { 
  PlaySquare, 
  Cpu, 
  Layers, 
  CheckCircle2, 
  AlertTriangle, 
  Activity,
  History,
  Workflow,
  Loader2
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function Runtime() {
  const { data: dashboard, isLoading: dashLoading } = useLiveDashboard();
  const { data: autoStatus, isLoading: autoLoading } = useAutonomousStatus();

  const isLoading = dashLoading || autoLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING RUNTIME INSTANCES...</span>
      </div>
    );
  }

  // Fetch active runtimes directly from actual monitored_services (fallback to live_production_monitoring)
  const runtimes = dashboard?.monitored_services || dashboard?.live_production_monitoring || [];

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <PlaySquare className="w-5 h-5 text-primary" />
            Runtime Manager
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Monitor active compute runtimes, execution workers, and decision loop loops
          </p>
        </div>
        <div className="flex items-center gap-1.5 status-pill info text-[10px]">
          <Workflow className="w-3.5 h-3.5" />
          LOOP ACTIVE
        </div>
      </header>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Runtimes Table */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">Active Compute Nodes</span>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[10px] divide-y divide-border">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="pb-2 font-medium">Node ID</th>
                  <th className="pb-2 font-medium">Workload (CPU)</th>
                  <th className="pb-2 font-medium">Memory</th>
                  <th className="pb-2 font-medium">Latency</th>
                  <th className="pb-2 font-medium">Last Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {runtimes.length > 0 ? (
                  runtimes.map((item, idx) => (
                    <tr key={idx} className="hover:bg-secondary/25">
                      <td className="py-3 font-semibold text-foreground flex items-center gap-1.5 uppercase">
                        <span className={`w-1.5 h-1.5 rounded-full ${item.status === 'CONNECTED' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                        {item.name}
                      </td>
                      <td className="py-3">
                        {item.cpu_percent !== null && item.cpu_percent !== undefined ? (
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-secondary h-1.5 rounded-full overflow-hidden border border-border/40">
                              <div className="bg-primary h-full rounded-full" style={{ width: `${item.cpu_percent}%` }} />
                            </div>
                            <span>{item.cpu_percent}%</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground font-mono">N/A</span>
                        )}
                      </td>
                      <td className="py-3">
                        {item.memory_percent !== null && item.memory_percent !== undefined ? (
                          `${item.memory_percent}%`
                        ) : (
                          <span className="text-muted-foreground font-mono">N/A</span>
                        )}
                      </td>
                      <td className="py-3">{item.response_time_ms} ms</td>
                      <td className="py-3 uppercase text-primary font-bold">{item.last_action || 'noop'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground italic">
                      No active compute nodes available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Autonomous Loop Controller */}
        <div className="premium-card flex flex-col gap-4 font-mono">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">
            RL Autonomy Loop
          </span>
          <div className="flex flex-col gap-3.5 mt-1.5">
            <div className="flex justify-between items-center bg-secondary/30 border border-border/40 px-3 py-2 rounded">
              <span>Status:</span>
              <span className="text-emerald-500 font-bold flex items-center gap-1">
                <span className="pulse-dot healthy" /> RUNNING
              </span>
            </div>
            
            <div className="flex justify-between items-center text-[10px] text-muted-foreground border-b border-border/20 pb-1">
              <span>Loop cycle:</span>
              <span className="text-foreground">Continuous</span>
            </div>

            <div className="flex justify-between items-center text-[10px] text-muted-foreground border-b border-border/20 pb-1">
              <span>Last Execution Event:</span>
              <span className="text-foreground font-semibold uppercase">{autoStatus?.last_action || runtimes[0]?.last_action || 'noop'}</span>
            </div>

            <div className="flex flex-col gap-1.5 mt-2">
              <span className="text-[10px] text-muted-foreground uppercase">Autonomy Directives:</span>
              <div className="text-[10px] bg-secondary/20 border border-border p-2.5 rounded text-muted-foreground leading-relaxed">
                Rules require <strong>RL Agent</strong> suggestions to pass Shakti E2E governance contract checking.
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Decision logs queue */}
      <section className="premium-card flex flex-col gap-4 mt-2">
        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">
          Autonomous Queue Workload (Historical decisions)
        </span>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px] divide-y divide-border">
            <thead>
              <tr className="text-muted-foreground">
                <th className="pb-2 font-medium">Timestamp</th>
                <th className="pb-2 font-medium">Action</th>
                <th className="pb-2 font-medium">Justification</th>
                <th className="pb-2 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {autoStatus?.recent_autonomous_decisions && autoStatus.recent_autonomous_decisions.length > 0 ? (
                autoStatus.recent_autonomous_decisions.map((dec: any, idx: number) => (
                  <tr key={idx} className="hover:bg-secondary/20">
                    <td className="py-2.5 text-muted-foreground">{dec.timestamp ? new Date(dec.timestamp).toLocaleTimeString() : '--'}</td>
                    <td className="py-2.5 text-primary font-bold uppercase">{dec.selected_action || dec.action || 'noop'}</td>
                    <td className="py-2.5 text-foreground leading-relaxed">{dec.reason}</td>
                    <td className="py-2.5 font-bold text-foreground">{(dec.confidence * 100).toFixed(1)}%</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-muted-foreground italic">No decisions recorded in loop current cycles.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
}
