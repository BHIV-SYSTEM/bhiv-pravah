'use client';

import React, { useState } from 'react';
import { useObserverEvents, useUnifiedRegistryTrace } from '../../hooks/useBackend';
import type { TelemetryEvent } from '../../types';
import { 
  Terminal, 
  Search, 
  Filter, 
  Database, 
  Activity, 
  ArrowRight,
  Info,
  Loader2,
  ShieldCheck
} from 'lucide-react';

export default function Telemetry() {
  const [limit, setLimit] = useState(100);
  const { data: eventsData, isLoading: eventsLoading, refetch } = useObserverEvents(limit);
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedService, setSelectedService] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');

  // Unified trace ID search
  const [traceInput, setTraceInput] = useState('');
  const [searchTraceId, setSearchTraceId] = useState<string | null>(null);
  
  const { data: traceData, isLoading: traceLoading, error: traceError } = useUnifiedRegistryTrace(searchTraceId);

  const handleTraceSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (traceInput.trim()) {
      setSearchTraceId(traceInput.trim());
    } else {
      setSearchTraceId(null);
    }
  };

  if (eventsLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING TELEMETRY STREAM...</span>
      </div>
    );
  }

  const events: TelemetryEvent[] = eventsData?.events || [];

  // Filter events
  const filteredEvents = events.filter((ev: TelemetryEvent) => {
    const matchesSearch = searchQuery ? JSON.stringify(ev).toLowerCase().includes(searchQuery.toLowerCase()) : true;
    const matchesService = selectedService === 'all' ? true : ev.service.toLowerCase() === selectedService.toLowerCase();
    const matchesStatus = selectedStatus === 'all' ? true : ev.status.toLowerCase() === selectedStatus.toLowerCase();
    return matchesSearch && matchesService && matchesStatus;
  });

  // Extract unique services and statuses for filtering options
  const uniqueServices = Array.from(
    new Set(
      events
        .map((e: any) => (e.service || '').toLowerCase().trim())
        .filter(Boolean)
    )
  );
  const uniqueStatuses = Array.from(
    new Set(
      events
        .map((e: any) => (e.status || '').toLowerCase().trim())
        .filter(Boolean)
    )
  );

  const getStatusClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy': return 'status-pill healthy';
      case 'degraded': return 'status-pill degraded';
      case 'error':
      case 'unreachable':
      case 'crashed': return 'status-pill critical';
      default: return 'status-pill info';
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Terminal className="w-5 h-5 text-primary" />
            Telemetry Stream & Diagnostics
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5 font-sans">
            Audit real-time incoming events, HTTP status codes, sanitized error diagnostics (no raw HTML dumps), and lineage traces.
          </p>
        </div>
      </header>

      {/* Main events table list with filters */}
      <section className="premium-card flex flex-col gap-4">
        
        {/* Filters Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/40 pb-3">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Active Telemetry Logs</span>
          
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="flex items-center gap-1.5 bg-secondary/40 border border-border px-2 py-1.5 rounded-lg w-40">
              <Search className="w-3.5 h-3.5 text-muted-foreground" />
              <input 
                type="text"
                placeholder="Search..."
                className="bg-transparent border-0 outline-none w-full text-[10px] text-foreground placeholder-muted-foreground"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Service filter */}
            <select 
              className="bg-secondary/40 text-muted-foreground border border-border rounded-lg px-2 py-1.5 outline-none font-mono text-[10px]"
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
            >
              <option value="all">All Services</option>
              {uniqueServices.map((svc, i) => (
                <option key={i} value={svc}>{svc.toUpperCase()}</option>
              ))}
            </select>

            {/* Status filter */}
            <select 
              className="bg-secondary/40 text-muted-foreground border border-border rounded-lg px-2 py-1.5 outline-none font-mono text-[10px]"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
            >
              <option value="all">All Statuses</option>
              {uniqueStatuses.map((st, i) => (
                <option key={i} value={st}>{st.toLowerCase()}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Table with Requirement 2 Diagnostics (HTTP Status Code, Failure Category, Sanitized Detail) */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px] divide-y divide-border">
            <thead>
              <tr className="text-muted-foreground">
                <th className="pb-2 font-medium">Time</th>
                <th className="pb-2 font-medium">Observed Source</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">HTTP Code</th>
                <th className="pb-2 font-medium">Category</th>
                <th className="pb-2 font-medium">Latency</th>
                <th className="pb-2 font-medium">Sanitized Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {filteredEvents.length > 0 ? (
                filteredEvents.map((ev: TelemetryEvent, idx: number) => (
                  <tr key={idx} className="hover:bg-secondary/20 transition-colors">
                    <td className="py-2.5 text-muted-foreground">{new Date(ev.ts + (ev.ts.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()}</td>
                    <td className="py-2.5 font-semibold text-foreground uppercase">{ev.service}</td>
                    <td className="py-2.5">
                      <span className={getStatusClass(ev.status)}>{ev.status}</span>
                    </td>
                    <td className="py-2.5 font-mono">
                      {ev.http_status ? (
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${ev.http_status >= 500 ? 'bg-rose-500/20 text-rose-400' : (ev.http_status >= 400 ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400')}`}>
                          {ev.http_status}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="py-2.5 text-muted-foreground uppercase text-[9px]">
                      {ev.failure_category || 'nominal'}
                    </td>
                    <td className="py-2.5">{ev.latency_ms} ms</td>
                    <td className="py-2.5 text-muted-foreground max-w-sm truncate" title={ev.sanitized_detail || ev.detail}>
                      {ev.sanitized_detail || ev.detail || '-'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-muted-foreground italic">No telemetry logs found matching filter criteria.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
}
