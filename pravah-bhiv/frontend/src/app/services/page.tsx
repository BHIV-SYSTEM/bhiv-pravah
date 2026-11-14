'use client';

import React from 'react';
import { useObserverStatus, usePostOverride, useDependencyTopology } from '../../hooks/useBackend';
import type { DependencyNode } from '../../types';
import { ServiceUrlLink } from '../../components/ServiceUrlLink';
import {
  Activity,
  RefreshCw,
  HelpCircle,
  ExternalLink,
  ShieldCheck,
  Zap,
  Server,
  Layers,
  Loader2,
  GitFork,
  ArrowRight
} from 'lucide-react';
import { toast } from 'sonner';

export default function Services() {
  const { data: observerStatus, isLoading, refetch } = useObserverStatus();
  const { data: topologyData } = useDependencyTopology();
  const postOverride = usePostOverride();

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING SERVICE TOPOLOGY...</span>
      </div>
    );
  }

  const services = observerStatus ? Object.entries(observerStatus.services).map(([name, info]) => ({
    name,
    ...info,
  })) : [];

  const handleRestart = (name: string) => {
    toast.promise(
      postOverride.mutateAsync({
        app_name: name,
        action: 'clear_freeze'
      }),
      {
        loading: `Sending restart/recovery request for ${name}...`,
        success: `Sent recovery trigger to ${name}`,
        error: `Failed to recover ${name}`
      }
    );
  };

  const getCanonicalBadge = (status: string) => {
    const s = (status || '').toLowerCase();
    if (s === 'healthy') return 'status-pill healthy';
    if (s === 'degraded') return 'status-pill degraded';
    if (s === 'unreachable' || s === 'critical' || s === 'error') return 'status-pill critical';
    if (s === 'stale') return 'bg-purple-500/20 text-purple-400 border border-purple-500/40 px-2 py-0.5 rounded text-[9px] font-bold';
    return 'bg-zinc-500/20 text-zinc-400 border border-zinc-500/40 px-2 py-0.5 rounded text-[9px] font-bold';
  };

  const topologyNodes: DependencyNode[] = topologyData?.topology || [];

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">

      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary" />
            Ecosystem Services & Dependencies
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5 font-sans">
            Inspect canonical health states, failure diagnostics, network URLs, and cascading dependency graphs.
          </p>
        </div>
      </header>

      {/* Services List Table */}
      <section className="premium-card flex flex-col gap-4">
        <div className="flex justify-between items-center border-b border-border/40 pb-2">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Canonical Service Health Status</span>
          <button
            onClick={() => refetch()}
            className="p-1 hover:text-primary transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full text-left text-[10px] divide-y divide-border min-w-[900px] table-auto">
            <thead>
              <tr className="text-muted-foreground border-b border-border/40">
                <th className="py-2.5 px-3 font-medium whitespace-nowrap w-[170px]">Service name</th>
                <th className="py-2.5 px-3 font-medium whitespace-nowrap w-[200px]">Network Endpoint URL</th>
                <th className="py-2.5 px-3 font-medium whitespace-nowrap w-[80px]">Latency</th>
                <th className="py-2.5 px-3 font-medium whitespace-nowrap w-[110px]">Canonical Status</th>
                <th className="py-2.5 px-3 font-medium whitespace-nowrap w-[70px]">Failures</th>
                <th className="py-2.5 px-3 font-medium whitespace-nowrap">Diagnostics / Reason</th>
                <th className="py-2.5 px-3 font-medium text-right whitespace-nowrap w-[90px]">Intervention</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {services.length > 0 ? (
                services.map((svc: any, idx: number) => (
                  <tr key={idx} className="hover:bg-secondary/20 transition-colors">
                    <td className="py-3 px-3 font-semibold text-foreground uppercase whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Server className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="truncate max-w-[140px]" title={svc.name}>{svc.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-muted-foreground select-all max-w-[200px] overflow-hidden">
                      <ServiceUrlLink url={svc.url} truncateClass="truncate max-w-[190px]" />
                    </td>
                    <td className="py-3 px-3 font-semibold text-foreground whitespace-nowrap font-mono">{svc.latency_ms} ms</td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={getCanonicalBadge(svc.canonical_state || svc.status)}>
                        {(svc.canonical_state || svc.status).toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={(svc.consecutive_failures || 0) > 0 ? 'text-rose-400 font-bold' : 'text-muted-foreground'}>
                        {svc.consecutive_failures || 0}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-muted-foreground max-w-[200px] truncate" title={svc.failure_reason || 'Operational'}>
                      {svc.failure_reason || 'Operational'}
                    </td>
                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleRestart(svc.name)}
                        className="px-2 py-1 bg-secondary hover:bg-border text-foreground hover:text-primary font-sans font-bold text-[9px] rounded transition-colors inline-flex items-center gap-1 ml-auto"
                      >
                        <Zap className="w-2.5 h-2.5" /> Recover
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-muted-foreground italic">
                    No active ecosystem services found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Requirement 6: Hierarchical Dependency Graph View */}
      <section className="premium-card flex flex-col gap-4">
        <div className="flex justify-between items-center border-b border-border/40 pb-2">
          <div>
            <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <GitFork className="w-4 h-4 text-primary" />
              Hierarchical Dependency & Cascading Impact Topology
            </span>
            <p className="text-[10px] text-muted-foreground mt-0.5 font-sans">
              Tracing cascade risk from foundational components (Redis, DB) through APIs to user-facing products.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {topologyNodes.map((node: DependencyNode, i: number) => (
            <div key={i} className="bg-secondary/30 border border-border/50 rounded-lg p-3 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-foreground uppercase">{node.service}</span>
                <span className="text-[9px] px-1.5 py-0.5 bg-primary/10 text-primary border border-primary/20 rounded font-bold uppercase">{node.tier}</span>
              </div>
              <div className="flex flex-col gap-1 text-[10px] text-muted-foreground">
                <div className="flex items-center gap-1">
                  <span>Product:</span>
                  <span className="font-semibold text-foreground">{node.product}</span>
                </div>
                {node.dependencies && node.dependencies.length > 0 && (
                  <div className="flex flex-col gap-0.5 mt-1 border-t border-border/40 pt-1">
                    <span className="text-[9px] uppercase font-bold text-muted-foreground">Dependencies:</span>
                    {node.dependencies.map((dep, dIdx) => (
                      <div key={dIdx} className="flex items-center justify-between pl-1">
                        <span className="text-zinc-300">&bull; {dep.dependency}</span>
                        <span className="text-[9px] text-emerald-400">{dep.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

    </div>
  );
}
