'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useObserverEvents } from '../../hooks/useBackend';
import { TelemetryEvent } from '../../types';
import { 
  FileText, 
  Terminal, 
  Search, 
  Filter, 
  RefreshCw, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Loader2,
  ChevronDown,
  ChevronRight,
  Pause,
  Play
} from 'lucide-react';

export default function LiveLogs() {
  const [limit, setLimit] = useState(100);
  const [isPaused, setIsPaused] = useState(false);
  const { data: eventsData, isLoading, refetch, isFetching } = useObserverEvents(
    limit, 
    isPaused ? undefined : 2500
  );

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedService, setSelectedService] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(false);

  const events: TelemetryEvent[] = eventsData?.events || [];

  // Filter events
  const filteredEvents = events.filter((ev) => {
    const matchesSearch = searchQuery
      ? ev.service.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ev.status.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ev.detail.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    const matchesService = selectedService === 'all' ? true : ev.service === selectedService;
    const matchesStatus = selectedStatus === 'all' ? true : ev.status.toLowerCase() === selectedStatus.toLowerCase();
    return matchesSearch && matchesService && matchesStatus;
  });

  // Extract unique services
  const uniqueServices = Array.from(new Set(events.map((e) => e.service))).sort();
  const healthyCount = events.filter((e) => e.status.toLowerCase() === 'healthy').length;
  const degradedCount = events.filter((e) => e.status.toLowerCase() !== 'healthy').length;

  const toggleRow = (idx: number) => {
    setExpandedRows((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">INITIALIZING OBSERVER LIVE STREAM...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            Live Logs Console
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real-time streaming telemetry and execution audit events captured from Observer daemon (Port 8600)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[11px] font-sans font-medium transition-colors ${
              isPaused 
                ? 'bg-amber-500/10 text-amber-500 border-amber-500/30' 
                : 'bg-secondary text-muted-foreground hover:text-foreground border-border'
            }`}
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            {isPaused ? 'Resume Stream' : 'Pause Stream'}
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-secondary hover:bg-secondary/80 text-foreground text-[11px] font-sans font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-primary' : ''}`} />
            Refresh
          </button>
          <div className="flex items-center gap-1.5 status-pill healthy text-[10px]">
            <span className={`pulse-dot ${isPaused ? 'degraded' : 'healthy'}`} />
            {isPaused ? 'PAUSED' : 'LIVE'}
          </div>
        </div>
      </header>

      {/* Top Metrics Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Captured Events</span>
          <span className="text-xl font-bold text-foreground font-sans">{events.length}</span>
          <div className="absolute right-3 top-3 opacity-15">
            <Terminal className="w-8 h-8 text-primary" />
          </div>
        </div>

        <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Healthy State Events</span>
          <span className="text-xl font-bold text-emerald-500 font-sans">{healthyCount}</span>
          <div className="absolute right-3 top-3 opacity-15">
            <CheckCircle2 className="w-8 h-8 text-emerald-500" />
          </div>
        </div>

        <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Degraded / Anomaly Events</span>
          <span className="text-xl font-bold text-amber-500 font-sans">{degradedCount}</span>
          <div className="absolute right-3 top-3 opacity-15">
            <AlertTriangle className="w-8 h-8 text-amber-500" />
          </div>
        </div>

        <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Observed Service Channels</span>
          <span className="text-xl font-bold text-foreground font-sans">{uniqueServices.length}</span>
          <div className="absolute right-3 top-3 opacity-15">
            <Activity className="w-8 h-8 text-primary" />
          </div>
        </div>
      </section>

      {/* Filter and Control Bar */}
      <section className="premium-card flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="flex flex-1 gap-2 w-full sm:w-auto items-center">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search event logs by keyword, service, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8.5 pr-3 py-2 bg-background border border-border rounded-lg text-xs outline-none focus:border-primary placeholder-muted-foreground"
            />
          </div>

          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground outline-none focus:border-primary"
          >
            <option value="all">All Services ({uniqueServices.length})</option>
            {uniqueServices.map((svc) => (
              <option key={svc} value={svc}>
                {svc}
              </option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground outline-none focus:border-primary"
          >
            <option value="all">All Statuses</option>
            <option value="healthy">Healthy</option>
            <option value="degraded">Degraded</option>
          </select>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <label className="flex items-center gap-2 cursor-pointer text-muted-foreground hover:text-foreground select-none">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-border"
            />
            <span className="text-[11px]">Auto-scroll</span>
          </label>
          <span className="text-[10px] text-muted-foreground border-l border-border pl-3">
            Showing {filteredEvents.length} / {events.length}
          </span>
        </div>
      </section>

      {/* Terminal Output Viewer */}
      <section className="premium-card flex flex-col gap-0 p-0 overflow-hidden border border-border bg-card/60">
        <div className="bg-secondary/40 border-b border-border/60 px-4 py-2.5 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block" />
            <span className="ml-2 font-semibold text-foreground/80">OBSERVER TELEMETRY STREAM (/api/events)</span>
          </div>
          <span>Refreshed: {new Date().toLocaleTimeString()}</span>
        </div>

        <div className="overflow-x-auto max-h-[600px] overflow-y-auto divide-y divide-border/40">
          {filteredEvents.length > 0 ? (
            filteredEvents.map((ev, idx) => {
              const isHealthy = ev.status.toLowerCase() === 'healthy';
              const isExpanded = !!expandedRows[idx];

              return (
                <div key={idx} className="flex flex-col hover:bg-secondary/20 transition-colors">
                  <div 
                    onClick={() => toggleRow(idx)}
                    className="flex items-center gap-3 px-4 py-2.5 cursor-pointer select-none text-[11px]"
                  >
                    <button className="text-muted-foreground hover:text-foreground">
                      {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                    
                    <span className="text-muted-foreground w-24 shrink-0 font-mono text-[10px]">
                      {ev.ts ? new Date(ev.ts).toLocaleTimeString() : '--:--:--'}
                    </span>

                    <span className="font-semibold text-foreground shrink-0 uppercase w-44 truncate">
                      {ev.service}
                    </span>

                    <span className={`status-pill ${isHealthy ? 'healthy' : 'degraded'} shrink-0 text-[9px]`}>
                      {ev.status.toUpperCase()}
                    </span>

                    <span className="text-muted-foreground/80 shrink-0 font-mono text-[10px] w-20">
                      {ev.latency_ms ? `${Math.round(ev.latency_ms)} ms` : '--'}
                    </span>

                    <span className="text-muted-foreground truncate flex-1 font-mono text-[10px]">
                      {ev.detail}
                    </span>
                  </div>

                  {isExpanded && (
                    <div className="bg-black/30 border-t border-border/40 px-8 py-3 flex flex-col gap-2">
                      <div className="flex justify-between items-center text-[10px] text-muted-foreground border-b border-border/30 pb-1">
                        <span>Timestamp: {ev.ts}</span>
                        <span>Latency: {ev.latency_ms} ms</span>
                      </div>
                      <pre className="text-[10px] text-muted-foreground bg-black/40 border border-border/40 p-3 rounded overflow-x-auto">
                        {(() => {
                          try {
                            return JSON.stringify(JSON.parse(ev.detail), null, 2);
                          } catch {
                            return ev.detail;
                          }
                        })()}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="py-16 text-center text-muted-foreground italic flex flex-col items-center gap-2">
              <Clock className="w-6 h-6 text-muted-foreground/40" />
              <span>No telemetry event logs match the current filters.</span>
            </div>
          )}
          <div ref={terminalEndRef} />
        </div>
      </section>

    </div>
  );
}
