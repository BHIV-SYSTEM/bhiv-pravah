'use client';

import React, { useState } from 'react';
import { useObserverLineage, useLineageReplay, useVerifyLineage } from '../../hooks/useBackend';
import ReplayVisualizer from '../../components/ReplayVisualizer';
import { 
  RefreshCw, 
  Search, 
  CheckCircle2, 
  XCircle, 
  ShieldCheck, 
  Clock, 
  Cpu, 
  ArrowRight,
  Database,
  Loader2
} from 'lucide-react';

export default function Replay() {
  const { data: lineageData, isLoading: indexLoading } = useObserverLineage();
  
  const [executionInput, setExecutionInput] = useState('');
  const [activeExecId, setActiveExecId] = useState<string | null>(null);

  const { data: replay, isLoading: replayLoading, error: replayError } = useLineageReplay(activeExecId);
  const { data: verify, isLoading: verifyLoading } = useVerifyLineage(activeExecId);

  const handleReplaySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (executionInput.trim()) {
      setActiveExecId(executionInput.trim());
    } else {
      setActiveExecId(null);
    }
  };

  const selectExecution = (execId: string) => {
    setExecutionInput(execId);
    setActiveExecId(execId);
  };

  const isLoading = indexLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING EVIDENCE BUNDLES...</span>
      </div>
    );
  }

  const bundles = lineageData?.lineages || [];

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-primary" />
            Replay Engine
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit deterministic execution chains and cryptographically attest historical actions
          </p>
        </div>
      </header>

      {/* Audit Tool Input */}
      <section className="premium-card flex flex-col gap-4">
        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <Database className="w-4 h-4 text-primary" />
          Execution Lineage Replay Audit
        </span>

        <form onSubmit={handleReplaySubmit} className="flex gap-2">
          <input 
            type="text"
            placeholder="Input execution_id (e.g. ex-abc123xyz)"
            className="flex-1 bg-secondary/40 text-foreground border border-border rounded-lg px-3 py-2 outline-none font-mono focus:border-primary text-xs"
            value={executionInput}
            onChange={(e) => setExecutionInput(e.target.value)}
          />
          <button 
            type="submit"
            className="bg-primary hover:opacity-90 text-primary-foreground text-[10px] px-4 py-2 rounded-lg font-sans font-bold flex items-center gap-1.5 shrink-0"
          >
            Replay Lineage <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </form>

        {/* Loading and Error States */}
        {replayLoading && (
          <div className="flex items-center gap-2 text-muted-foreground text-xs py-2">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            <span>Replaying transition trace loops...</span>
          </div>
        )}

        {replayError && (
          <div className="text-rose-500 bg-rose-500/10 border border-rose-500/20 p-3 rounded-lg">
            Replay failed: {replayError.message || 'Execution ID not found in transaction journal.'}
          </div>
        )}

        {/* Replay Details */}
        {replay && (
          <div className="flex flex-col gap-5 border border-border rounded-lg p-4 bg-secondary/15 mt-2 animate-fade-in">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span className="font-bold text-foreground uppercase">Attestation Report: {replay.execution_id}</span>
              <div className="flex gap-2">
                <span className={`status-pill ${replay.valid ? 'healthy' : 'critical'}`}>
                  Transition: {replay.valid ? 'VALID' : 'INVALID'}
                </span>
                {verify && (
                  <span className={`status-pill ${verify.hash_chain_valid ? 'healthy' : 'critical'}`}>
                    Hash Chain: {verify.hash_chain_valid ? 'SECURE' : 'COMPROMISED'}
                  </span>
                )}
              </div>
            </div>

            {/* Visualizer Flow Graph */}
            <ReplayVisualizer events={replay.events} />

            {/* Event list */}
            <div className="flex flex-col gap-2 mt-2">
              <span className="text-[10px] text-muted-foreground uppercase">Transition Step Timeline:</span>
              <div className="flex flex-col gap-2">
                {replay.events.map((ev: any, idx: number) => (
                  <div key={idx} className="flex gap-3 items-start border-l border-border pl-3.5 py-1">
                    <div className="flex-1 flex flex-col gap-1">
                      <div className="flex justify-between">
                        <span className="font-bold text-foreground capitalize">{ev.state || ev.event_type}</span>
                        <span className="text-[9px] text-muted-foreground">{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '--'}</span>
                      </div>
                      <pre className="text-[9px] text-muted-foreground bg-black/30 border border-border/40 p-2 rounded max-h-16 overflow-y-auto">
                        {JSON.stringify(ev.details || ev.payload || {}, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Evidence index list */}
      <section className="premium-card flex flex-col gap-4">
        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">
          Registered Evidence Registry (Select ID to Replay)
        </span>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px] divide-y divide-border">
            <thead>
              <tr className="text-muted-foreground">
                <th className="pb-2 font-medium">Timestamp</th>
                <th className="pb-2 font-medium">Bundle ID</th>
                <th className="pb-2 font-medium">Execution ID</th>
                <th className="pb-2 font-medium">Decision Type</th>
                <th className="pb-2 font-medium">Authority Chain</th>
                <th className="pb-2 font-medium text-right">Audit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {bundles.length > 0 ? (
                bundles.map((bundle, idx) => (
                  <tr key={idx} className="hover:bg-secondary/20 transition-colors">
                    <td className="py-2.5 text-muted-foreground">{bundle.produced_at ? new Date(bundle.produced_at).toLocaleString() : '--'}</td>
                    <td className="py-2.5 font-semibold text-foreground truncate max-w-[100px]">{bundle.bundle_id}</td>
                    <td className="py-2.5 text-muted-foreground truncate max-w-[120px] font-mono">{bundle.execution_id}</td>
                    <td className="py-2.5">
                      <span className="status-pill info">{bundle.decision_type || 'Orchestrate'}</span>
                    </td>
                    <td className="py-2.5 text-primary-foreground/75 font-semibold">
                      {Array.isArray(bundle.authority_chain) ? bundle.authority_chain.join(' -> ') : String(bundle.authority_chain || '--')}
                    </td>
                    <td className="py-2.5 text-right">
                      <button 
                        onClick={() => selectExecution(bundle.execution_id)}
                        className="px-2 py-1 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded font-sans font-bold text-[9px] transition-colors"
                      >
                        Replay
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground italic">No evidence bundles registered yet. Run backend simulators to emit logs.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
}
