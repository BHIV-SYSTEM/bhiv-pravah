'use client';

import React, { useState } from 'react';
import { useObserverStatus } from '../../hooks/useBackend';
import { 
  Shield, 
  Search, 
  RefreshCw, 
  HelpCircle, 
  ExternalLink,
  ChevronDown,
  Info,
  Loader2
} from 'lucide-react';

export default function Observer() {
  const { data: observerStatus, isLoading, isError, refetch } = useObserverStatus();
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">CONNECTING TO OBSERVER DAEMON...</span>
      </div>
    );
  }

  if (isError || !observerStatus) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-4 text-center">
        <Shield className="w-12 h-12 text-rose-500" />
        <div>
          <h3 className="font-bold text-sm font-sans">OBSERVER DAEMON OFFLINE</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm">
            Failed to connect to the Pravah Observer Server on port 8600. Ensure the uvicorn server is running.
          </p>
        </div>
        <button 
          onClick={() => refetch()}
          className="px-4 py-2 bg-primary text-primary-foreground font-sans text-xs font-semibold rounded-lg hover:opacity-90 transition-opacity"
        >
          Reconnect
        </button>
      </div>
    );
  }

  const services = Object.entries(observerStatus.services).map(([name, info]) => ({
    name,
    ...info,
  }));

  // Filter services
  const filteredServices = services.filter(svc => {
    const matchesSearch = svc.name.toLowerCase().includes(searchQuery.toLowerCase()) || svc.url.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = filterStatus === 'all' ? true : svc.status.toLowerCase() === filterStatus.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  const formatCheckedTime = (timestamp: string | null | undefined): string => {
    if (!timestamp) return 'N/A';
    try {
      const d = new Date(timestamp);
      return isNaN(d.getTime()) ? 'N/A' : d.toLocaleTimeString();
    } catch {
      return 'N/A';
    }
  };

  const getStatusClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy': return 'status-pill healthy';
      case 'degraded': return 'status-pill degraded';
      case 'unreachable':
      case 'timeout':
      case 'error': return 'status-pill critical';
      default: return 'status-pill info';
    }
  };

  const getPulseClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy': return 'pulse-dot healthy';
      case 'degraded': return 'pulse-dot degraded';
      case 'unreachable':
      case 'timeout':
      case 'error': return 'pulse-dot critical';
      default: return 'pulse-dot info';
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            Observer Panel
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Active health audits & event visibility across {services.length} ecosystem runtimes (Pravah observes, does not own)
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-border bg-card hover:bg-secondary rounded-lg transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </header>

      {/* Info Warning banner */}
      <div className="bg-secondary/20 border border-border/60 p-4 rounded-lg flex gap-3 text-muted-foreground leading-relaxed">
        <Info className="w-5 h-5 text-primary shrink-0 mt-0.5" />
        <div className="flex flex-col gap-1 font-sans text-xs">
          <span className="font-semibold text-foreground">Constitutional Limit Safeguard (TANTRA Governance)</span>
          <span>
            Pravah operates strictly in **read-only observation mode** for these product endpoints. It tails metric bundles and queries health parameters passively. It has zero operational override permissions on downstream databases or systems.
          </span>
        </div>
      </div>

      {/* Filters */}
      <section className="flex flex-wrap items-center justify-between gap-4 border-b border-border/40 pb-3">
        <div className="flex items-center gap-2 bg-secondary/40 border border-border px-3 py-1.5 rounded-lg w-64">
          <Search className="w-3.5 h-3.5 text-muted-foreground" />
          <input 
            type="text"
            placeholder="Search observed service or URL..."
            className="bg-transparent border-0 outline-none w-full text-[10px] text-foreground placeholder-muted-foreground"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="flex gap-2 font-sans">
          {['all', 'healthy', 'degraded', 'unreachable'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-lg border text-[10px] font-bold uppercase transition-all ${filterStatus === status ? 'bg-primary/10 text-primary border-primary' : 'bg-card text-muted-foreground border-border hover:text-foreground'}`}
            >
              {status}
            </button>
          ))}
        </div>
      </section>

      {/* Cards Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredServices.length > 0 ? (
          filteredServices.map((svc, idx) => (
            <div key={idx} className="premium-card flex flex-col justify-between gap-3 h-48 select-none group">
              <div className="flex flex-col gap-1.5">
                <span className="font-extrabold text-[11px] text-foreground uppercase tracking-wide truncate" title={svc.name}>
                  {svc.name}
                </span>
                <span className={`${getStatusClass(svc.status)} w-fit self-start`}>
                  {svc.status}
                </span>
                <span className="text-[9px] text-muted-foreground truncate font-mono select-all bg-secondary/35 px-1.5 py-0.5 rounded border border-border/40">
                  {svc.url}
                </span>
              </div>

              {/* Latency */}
              <div className="flex flex-col gap-0.5 mt-2">
                <span className="text-[9px] text-muted-foreground">LATENCY</span>
                <span className="text-xl font-bold tracking-tight text-primary flex items-baseline gap-0.5 font-sans">
                  {svc.latency_ms} <small className="text-[10px] font-mono font-medium text-muted-foreground">ms</small>
                </span>
              </div>

              {/* Footer */}
              <div className="flex justify-between items-center text-[8px] text-muted-foreground border-t border-border/40 pt-2 font-mono">
                <span>CHECKED {formatCheckedTime(svc.last_checked)}</span>
                {svc.detail && svc.detail !== 'connection refused' && svc.detail !== 'request timed out' && (
                  <span className="cursor-pointer hover:text-foreground underline truncate max-w-[80px]" title={svc.detail}>Payload Response</span>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-full py-16 text-center text-muted-foreground italic font-sans">
            No observed services match the filters.
          </div>
        )}
      </section>

    </div>
  );
}
