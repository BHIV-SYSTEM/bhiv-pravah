'use client';

import React from 'react';
import { useActionScope, useLiveDashboard } from '../../hooks/useBackend';
import { 
  Settings, 
  ShieldAlert, 
  Scale, 
  Heart, 
  HelpCircle,
  FolderOpen,
  Info,
  Loader2
} from 'lucide-react';

export default function Configuration() {
  const { data: actionScope, isLoading: scopeLoading } = useActionScope();
  const { data: dashboard, isLoading: dashLoading } = useLiveDashboard();

  const isLoading = scopeLoading || dashLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING SYSTEM DIRECTIVES...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            Governance Configuration
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit system environments, action boundaries, and constitutional safeguards
          </p>
        </div>
      </header>

      {/* TANTRA safeguards */}
      <section className="premium-card flex flex-col gap-4">
        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <Scale className="w-4 h-4 text-primary" />
          TANTRA Constitutional Safeguards
        </span>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-1 font-sans leading-relaxed">
          <div className="bg-secondary/35 border border-border/60 p-4 rounded-lg flex flex-col gap-1">
            <span className="font-extrabold text-[11px] text-foreground uppercase tracking-wide">1. Observability &ne; Authority</span>
            <span className="text-[10px] text-muted-foreground mt-1">
              Ecosystem metrics gather trace continuity data passively. Pravah holds zero down-line compute ownership or execution right over product runtimes.
            </span>
          </div>

          <div className="bg-secondary/35 border border-border/60 p-4 rounded-lg flex flex-col gap-1">
            <span className="font-extrabold text-[11px] text-foreground uppercase tracking-wide">2. Replay &ne; Truth</span>
            <span className="text-[10px] text-muted-foreground mt-1">
              Replay simulations prove state equivalence and trace recovery correctness, but must never rewrite active database states or operational logic.
            </span>
          </div>

          <div className="bg-secondary/35 border border-border/60 p-4 rounded-lg flex flex-col gap-1">
            <span className="font-extrabold text-[11px] text-foreground uppercase tracking-wide">3. Telemetry &ne; Governance</span>
            <span className="text-[10px] text-muted-foreground mt-1">
              Governance belongs strictly to human operators or sovereign constitutional systems. Telemetry reports parameters, it does not enforce law.
            </span>
          </div>

          <div className="bg-secondary/35 border border-border/60 p-4 rounded-lg flex flex-col gap-1">
            <span className="font-extrabold text-[11px] text-foreground uppercase tracking-wide">4. Visibility &ne; Execution</span>
            <span className="text-[10px] text-muted-foreground mt-1">
              Visibility logs establish full audits, but provide zero permission to modify live configurations or user-active variables.
            </span>
          </div>
        </div>
      </section>

      {/* Grid: Actions Scope & Environment settings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left: Environment Allowed Actions */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">Allowed Actions Registry Matrix</span>
          
          <div className="flex flex-col gap-3">
            {actionScope && Object.entries(actionScope).map(([env, actions]) => (
              <div key={env} className="flex justify-between items-center bg-secondary/20 border border-border/40 px-3 py-2 rounded-lg">
                <span className="font-bold text-foreground uppercase">{env}</span>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(actions) ? actions : []).map((act, i) => (
                    <span key={i} className="bg-secondary border border-border text-muted-foreground text-[8px] px-2 py-0.5 rounded font-mono uppercase">
                      {act}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Policy Snapshot */}
        <div className="premium-card flex flex-col gap-4">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">
            AI Policy Parameters
          </span>
          
          <div className="flex flex-col gap-3">
            {(Array.isArray(dashboard?.ai_learning_status) ? dashboard!.ai_learning_status : []).map((item, idx) => (
              <div key={idx} className="flex justify-between items-center text-[10px] border-b border-border/40 pb-1.5 last:border-0 last:pb-0">
                <span className="text-muted-foreground">{item.label}:</span>
                <span className="text-foreground font-bold">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
}
