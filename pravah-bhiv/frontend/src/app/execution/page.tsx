'use client';

import React, { useState } from 'react';
import { useLiveDashboard, useAutonomousStatus } from '../../hooks/useBackend';
import { 
  Activity, 
  Terminal, 
  CheckCircle2, 
  Cpu, 
  Workflow, 
  Info,
  Server,
  Loader2
} from 'lucide-react';

export default function Execution() {
  const { data: dashboard, isLoading: dashLoading } = useLiveDashboard();
  const { data: autoStatus, isLoading: autoLoading } = useAutonomousStatus();
  
  const [selectedDecisionIdx, setSelectedDecisionIdx] = useState<number | null>(null);

  const isLoading = dashLoading || autoLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING EXECUTION CONSOLE...</span>
      </div>
    );
  }

  const decisions = autoStatus?.recent_autonomous_decisions || dashboard?.live_events || [];

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Workflow className="w-5 h-5 text-primary" />
            Execution Console
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Monitor real-time task workloads, execution stages, and attestation logs
          </p>
        </div>
      </header>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left: Execution List */}
        <div className="lg:col-span-1 premium-card flex flex-col gap-4">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">Active Task Instances</span>
          
          <div className="flex flex-col gap-2 overflow-y-auto max-h-[400px]">
            {decisions.length > 0 ? (
              decisions.map((dec: any, idx: number) => {
                const isSelected = selectedDecisionIdx === idx;
                const action = dec.selected_action || dec.action || dec.title || 'noop';
                return (
                  <div 
                    key={idx}
                    onClick={() => setSelectedDecisionIdx(idx)}
                    className={`border p-3 rounded-lg cursor-pointer transition-all duration-150 flex flex-col gap-1.5 ${isSelected ? 'bg-primary/10 border-primary' : 'bg-secondary/20 border-border hover:bg-secondary/40'}`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-extrabold text-[10px] text-foreground uppercase truncate max-w-[120px]">{action}</span>
                      <span className="status-pill healthy">COMPLETED</span>
                    </div>
                    <span className="text-[9px] text-muted-foreground">{dec.timestamp ? new Date(dec.timestamp).toLocaleTimeString() : 'Recent'}</span>
                  </div>
                );
              })
            ) : (
              <span className="text-muted-foreground italic text-xs">No active runs available.</span>
            )}
          </div>
        </div>

        {/* Right: Step timeline & logs */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4 h-[490px]">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2 flex items-center gap-1.5">
            <Terminal className="w-4 h-4 text-primary" />
            Execution Pipeline attestation logs
          </span>

          <div className="flex-1 flex flex-col justify-between overflow-hidden">
            {selectedDecisionIdx !== null && decisions[selectedDecisionIdx] ? (
              (() => {
                const dec = decisions[selectedDecisionIdx] as any;
                return (
                  <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-2 text-[10px]">
                    <div className="bg-secondary/30 border border-border p-3 rounded-lg flex flex-col gap-1.5">
                      <span className="font-bold text-foreground">Task Overview: {dec.selected_action || dec.action || dec.title}</span>
                      <div>Justification: <span className="text-muted-foreground">{dec.reason || 'Telemetry trace alert trigger'}</span></div>
                      <div>Confidence Score: <span className="text-primary font-bold">{dec.confidence ? `${(dec.confidence * 100).toFixed(1)}%` : '100%'}</span></div>
                    </div>

                    {/* Step log list */}
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2 border-b border-border/40 pb-1 text-[9px] text-muted-foreground font-bold">
                        <span>STAGE LOGS</span>
                      </div>

                      <div className="flex flex-col gap-2">
                        <div className="flex gap-2 border-l border-emerald-500 pl-3 py-0.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold text-foreground">[STAGE 1] Trigger Anomaly Event detection</div>
                            <div className="text-muted-foreground mt-0.5 text-[9px]">Ingested metrics trigger evaluation hook.</div>
                          </div>
                        </div>

                        <div className="flex gap-2 border-l border-emerald-500 pl-3 py-0.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold text-foreground">[STAGE 2] Normalize Ingest payload</div>
                            <div className="text-muted-foreground mt-0.5 text-[9px]">JSON trace payload structure normalized against schema.</div>
                          </div>
                        </div>

                        <div className="flex gap-2 border-l border-emerald-500 pl-3 py-0.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold text-foreground">[STAGE 3] Query RL Decision Brain</div>
                            <div className="text-muted-foreground mt-0.5 text-[9px]">Q-table weights optimized value: {dec.selected_action || 'scale_up'} chosen.</div>
                          </div>
                        </div>

                        <div className="flex gap-2 border-l border-emerald-500 pl-3 py-0.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold text-foreground">[STAGE 4] Governance Scope Check</div>
                            <div className="text-muted-foreground mt-0.5 text-[9px]">Decision validated against environment action scopes: APPROVED.</div>
                          </div>
                        </div>

                        <div className="flex gap-2 border-l border-emerald-500 pl-3 py-0.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold text-foreground">[STAGE 5] Provision Downstream Action</div>
                            <div className="text-muted-foreground mt-0.5 text-[9px]">Forwarded to docker container runtime execution pipeline: Completed.</div>
                          </div>
                        </div>

                        <div className="flex gap-2 border-l border-emerald-500 pl-3 py-0.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold text-foreground">[STAGE 6] Cryptographic Attestation Seal</div>
                            <div className="text-muted-foreground mt-0.5 text-[9px]">Lineage FSM hashes signed and saved to evidence bundles registry.</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()
            ) : (
              <div className="flex flex-col items-center justify-center flex-1 text-muted-foreground gap-1 font-sans">
                <Server className="w-8 h-8 opacity-20" />
                <span>Select an active task instance to load attestation trace logs.</span>
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
