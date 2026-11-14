'use client';

import React, { useState } from 'react';
import {
  useLiveDashboard,
  useIngestLink,
  useRemoveLink,
  useObserverEvents,
  useUnifiedProductHealth,
  useIncidents
} from '../hooks/useBackend';
import type { IncidentItem, UnifiedProductItem } from '../types';
import { ServiceUrlLink } from '../components/ServiceUrlLink';
import {
  Activity,
  Cpu,
  TrendingUp,
  AlertTriangle,
  Plus,
  Trash2,
  CheckCircle2,
  ShieldAlert,
  ArrowRightLeft,
  Loader2,
  AlertOctagon,
  Clock,
  Layers,
  Server
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { toast } from 'sonner';

export default function Dashboard() {
  const { data: dashboard, isLoading, isError, refetch } = useLiveDashboard();
  const { data: eventsData } = useObserverEvents(10);
  const { data: unifiedHealth } = useUnifiedProductHealth();
  const { data: incidentsData } = useIncidents();
  const ingestMutation = useIngestLink();
  const removeMutation = useRemoveLink();

  const [newLink, setNewLink] = useState('');

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">LOADING REAL-TIME METRICS...</span>
      </div>
    );
  }

  if (isError || !dashboard) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-4 text-center">
        <ShieldAlert className="w-12 h-12 text-rose-500" />
        <div>
          <h3 className="font-bold text-sm font-sans">CONTROL PLANE UNREACHABLE</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm">
            Failed to connect to the Decision Brain API. Ensure the backend stack is running and reachable.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-primary text-primary-foreground font-sans text-xs font-semibold rounded-lg hover:opacity-90 transition-opacity"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLink.trim()) return;

    toast.promise(ingestMutation.mutateAsync(newLink), {
      loading: 'Ingesting repository link...',
      success: (res) => {
        if (res.success) {
          setNewLink('');
          return `Successfully ingested: ${res.ingested_link?.name || newLink}`;
        }
        throw new Error(res.error || 'Failed to ingest link');
      },
      error: (err) => err.message
    });
  };

  const handleRemove = async (link: string) => {
    toast.promise(removeMutation.mutateAsync(link), {
      loading: 'Removing monitored link...',
      success: (res) => {
        if (res.success) {
          return 'Successfully removed from monitoring';
        }
        throw new Error(res.error || 'Failed to remove link');
      },
      error: (err) => err.message
    });
  };

  // Prepare chart data from actual backend monitored_services (fallback to legacy live_production_monitoring)
  const monitoring = Array.isArray(dashboard.monitored_services)
    ? dashboard.monitored_services
    : Array.isArray(dashboard.live_production_monitoring)
    ? dashboard.live_production_monitoring
    : [];

  const latencyData = monitoring.map(item => ({
    name: item.name,
    latency: item.response_time_ms,
    uptime: item.uptime_percent,
  }));

  const resourceData = monitoring
    .filter(item => item.cpu_percent !== null || item.memory_percent !== null)
    .map(item => ({
      name: item.name,
      cpu: item.cpu_percent,
      memory: item.memory_percent,
    }));

  // Health distribution
  const healthyCount = monitoring.filter(s => s.status === 'CONNECTED' || s.status === 'HEALTHY').length;
  const criticalCount = monitoring.filter(s => s.status === 'CRITICAL' || s.status === 'DISCONNECTED').length;
  const degradedCount = monitoring.filter(s => s.status === 'DEGRADED').length;

  const pieData = [
    { name: 'Healthy', value: healthyCount, color: '#10b981' },
    { name: 'Degraded', value: degradedCount, color: '#f59e0b' },
    { name: 'Critical', value: criticalCount, color: '#ef4444' },
  ].filter(d => d.value > 0);

  // Derive system health metrics cards from actual backend system_health object
  const healthCards = (() => {
    if (Array.isArray(dashboard.system_health)) {
      return dashboard.system_health.map((s: any) => ({
        label: s.label,
        value: s.value,
        isHealth: String(s.label).toLowerCase().includes('health'),
      }));
    }
    if (dashboard.system_health && typeof dashboard.system_health === 'object') {
      const sh = dashboard.system_health as any;
      return [
        {
          label: 'CPU Utilization',
          value: sh.cpu_utilization_pct !== null && sh.cpu_utilization_pct !== undefined ? `${sh.cpu_utilization_pct}%` : 'N/A',
          isHealth: false,
        },
        {
          label: 'Memory Utilization',
          value: sh.memory_utilization_pct !== null && sh.memory_utilization_pct !== undefined ? `${sh.memory_utilization_pct}%` : 'N/A',
          isHealth: false,
        },
        {
          label: 'System Status',
          value: sh.status || 'UNKNOWN',
          isHealth: true,
        },
        {
          label: 'Telemetry Collection',
          value: sh.collection_status ? String(sh.collection_status).toUpperCase() : 'AVAILABLE',
          isHealth: true,
        },
      ];
    }
    return [];
  })();

  const activeIncidents: IncidentItem[] = incidentsData?.incidents || [];
  const customerProducts: UnifiedProductItem[] = unifiedHealth?.products || [];
  const platformComponents: UnifiedProductItem[] = unifiedHealth?.platform_health?.services || [];

  const getCanonicalBadge = (state: string) => {
    const s = (state || '').toLowerCase();
    if (s === 'healthy') return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30';
    if (s === 'degraded') return 'bg-amber-500/10 text-amber-500 border-amber-500/30';
    if (s === 'unreachable') return 'bg-rose-500/10 text-rose-500 border-rose-500/30';
    if (s === 'stale') return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
    return 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30';
  };

  return (
    <div className="flex-1 flex flex-col gap-6 font-sans">

      {/* Dashboard Top Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground">
            {dashboard.environment ? `Pravah Decision Brain (${dashboard.environment.toUpperCase()})` : (dashboard.header?.title || 'System Dashboard')}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {dashboard.header?.subtitle || 'Live Telemetry'} &bull; Generated at {dashboard.generated_at ? new Date(dashboard.generated_at).toLocaleTimeString() : 'N/A'}
          </p>
        </div>
        <div className="flex items-center gap-1.5 status-pill healthy font-mono text-[10px]">
          <span className="pulse-dot healthy" />
          SYSTEM OPERATIONAL
        </div>
      </header>

      {/* Incident Correlation Alert Banner (Requirement 7) */}
      {activeIncidents.length > 0 && (
        <section className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 flex flex-col gap-2 font-mono text-xs shadow-lg animate-pulse">
          <div className="flex items-center gap-2 text-rose-400 font-bold tracking-wide">
            <AlertOctagon className="w-5 h-5" />
            <span>ACTIVE INCIDENT DETECTED ({activeIncidents.length} CORRELATED ALARM{activeIncidents.length > 1 ? 'S' : ''})</span>
          </div>
          {activeIncidents.map((inc: IncidentItem, i: number) => (
            <div key={i} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-rose-900/20 p-2.5 rounded border border-rose-800/40 text-[11px]">
              <div>
                <span className="font-bold text-foreground">[{inc.incident_id}] {inc.symptoms?.join(', ') || 'Service Alert'}</span> &bull;
                <span className="text-rose-300 ml-1">Products: {inc.affected_products?.join(', ') || 'Core'}</span> &bull;
                <span className="text-zinc-300 ml-1">Probable Source: {inc.probable_source}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="px-2 py-0.5 bg-rose-500/20 text-rose-300 border border-rose-500/40 rounded text-[9px] font-bold uppercase">{inc.severity}</span>
                <span className="text-[10px] text-zinc-400">{new Date(inc.started_at).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Requirement 5: Unified Product Health Scorecard */}
      <section className="premium-card flex flex-col gap-4 font-mono">
        <div className="flex justify-between items-center border-b border-border/60 pb-3">
          <div>
            <h3 className="font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
              <Layers className="w-4 h-4 text-primary" />
              Unified Product Health Scorecard
            </h3>
            <p className="text-[10px] text-muted-foreground mt-0.5 font-sans">
              Strictly separating customer-facing product services from internal Pravah platform components.
            </p>
          </div>
          <div className="text-[10px] text-muted-foreground">
            Platform Status: <span className="font-bold text-emerald-400">{unifiedHealth?.platform_health?.status || 'Healthy'}</span>
          </div>
        </div>

        {/* Customer Products Table */}
        <div className="flex flex-col gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Customer Products Tier</span>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[10px] divide-y divide-border">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="pb-2 font-medium">Product / URL</th>
                  <th className="pb-2 font-medium">State (Canonical)</th>
                  <th className="pb-2 font-medium">P95 Latency</th>
                  <th className="pb-2 font-medium">Consecutive Fails</th>
                  <th className="pb-2 font-medium">Failure Reason / Diagnostics</th>
                  <th className="pb-2 font-medium text-right">Last Successful Check</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {customerProducts.length > 0 ? (
                  customerProducts.map((p: UnifiedProductItem, idx: number) => (
                    <tr key={idx} className="hover:bg-secondary/20">
                      <td className="py-2.5 font-semibold text-foreground flex items-center gap-1.5">
                        <Server className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <div className="overflow-hidden">
                          <div>{p.name}</div>
                          <ServiceUrlLink url={p.url} truncateClass="text-[9px] max-w-[170px]" />
                        </div>
                      </td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded border text-[9px] font-bold uppercase ${getCanonicalBadge(p.status)}`}>
                          {p.status}
                        </span>
                      </td>
                      <td className="py-2.5 font-mono">{p.latency_p95_ms !== null && p.latency_p95_ms !== undefined ? `${p.latency_p95_ms}ms` : 'N/A'}</td>
                      <td className="py-2.5">
                        <span className={p.consecutive_failures > 0 ? 'text-rose-400 font-bold' : 'text-muted-foreground'}>
                          {p.consecutive_failures}
                        </span>
                      </td>
                      <td className="py-2.5 text-muted-foreground max-w-xs truncate" title={p.failure_reason || 'Operational'}>
                        {p.failure_reason || 'No active degradation'}
                      </td>
                      <td className="py-2.5 text-right text-muted-foreground">
                        {p.last_successful_check ? new Date(p.last_successful_check).toLocaleTimeString() : 'Never'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-muted-foreground italic">
                      No customer product endpoints registered yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pravah Internal Platform Components */}
        <div className="flex flex-col gap-2 pt-2 border-t border-border/40">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Pravah Platform Core</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {platformComponents.map((comp: UnifiedProductItem, idx: number) => (
              <div key={idx} className="bg-secondary/30 border border-border/40 rounded-lg p-2.5 flex items-center justify-between">
                <div className="flex flex-col overflow-hidden max-w-[140px]">
                  <span className="text-xs font-bold text-foreground truncate">{comp.name}</span>
                  <ServiceUrlLink url={comp.url} truncateClass="text-[9px] max-w-[130px]" />
                </div>
                <span className={`px-2 py-0.5 rounded border text-[9px] font-bold uppercase ${getCanonicalBadge(comp.status)}`}>
                  {comp.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Top 4 Stats Rows */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {healthCards.map((s, idx) => (
          <div key={idx} className="premium-card flex flex-col gap-1 relative overflow-hidden">
            <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">{s.label}</div>
            <div className="text-xl font-bold tracking-tight text-foreground">{s.value}</div>
            <div className="absolute right-3 top-3 opacity-15">
              {s.isHealth ? <Activity className="w-8 h-8 text-emerald-500" /> : <Cpu className="w-8 h-8 text-primary" />}
            </div>
          </div>
        ))}
      </section>

      {/* Charts Grid */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Latency History */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4">
          <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground font-mono">Response Times (ms)</h4>
          <div className="h-64 w-full text-[10px] font-mono">
            {latencyData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={latencyData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--muted-foreground)" />
                  <YAxis stroke="var(--muted-foreground)" />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
                  />
                  <Area type="monotone" dataKey="latency" name="Latency (ms)" stroke="var(--primary)" fillOpacity={1} fill="url(#colorLatency)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground italic font-mono">
                No latency telemetry available (No active compute nodes monitored)
              </div>
            )}
          </div>
        </div>

        {/* Status Distribution */}
        <div className="premium-card flex flex-col gap-4">
          <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground font-mono">Service Distribution</h4>
          <div className="flex-1 flex flex-col items-center justify-center min-h-[220px]">
            {pieData.length > 0 ? (
              <div className="h-44 w-full text-[10px] font-mono relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={65}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                {/* Center metric */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-xl font-bold">{monitoring.length}</span>
                  <span className="text-[9px] text-muted-foreground font-sans">MONITORED</span>
                </div>
              </div>
            ) : (
              <span className="text-muted-foreground text-xs font-mono">No nodes active.</span>
            )}
            <div className="flex gap-4 justify-center text-[10px] font-mono mt-2">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-emerald-500" /> Healthy ({healthyCount})</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-amber-500" /> Degraded ({degradedCount})</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-rose-500" /> Critical ({criticalCount})</span>
            </div>
          </div>
        </div>
      </section>

      {/* Resource Util & failover row */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Resource Usage bar chart */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4">
          <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground font-mono">Resource Utilization</h4>
          <div className="h-56 w-full text-[10px] font-mono">
            {resourceData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={resourceData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--muted-foreground)" />
                  <YAxis stroke="var(--muted-foreground)" />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)' }}
                    formatter={(value: any, name: any) => [value !== null && value !== undefined ? `${value}%` : 'N/A', name]}
                  />
                  <Bar dataKey="cpu" name="CPU %" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="memory" name="Memory %" fill="var(--secondary-foreground)" opacity={0.3} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground italic">
                No active compute node telemetry available (External links: N/A)
              </div>
            )}
          </div>
        </div>

        {/* Failover Domain Config */}
        <div className="premium-card flex flex-col gap-4 font-mono">
          <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Failover Orchestrator</h4>
          <div className="flex flex-col gap-3.5 mt-2">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span className="text-xs text-muted-foreground">Active Gate:</span>
              <span className="text-xs font-extrabold text-primary flex items-center gap-1">
                <ArrowRightLeft className="w-3.5 h-3.5" />
                {dashboard.auto_failover_status?.active_domain || 'N/A'}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-[10px] text-muted-foreground uppercase">Domain Failover Queue:</span>
              {(Array.isArray(dashboard.auto_failover_status?.domains) ? dashboard.auto_failover_status.domains : []).map((dom, i) => (
                <div key={i} className="flex justify-between items-center bg-secondary/30 border border-border/40 px-3 py-1.5 rounded text-[10px]">
                  <span>{dom.name}</span>
                  <span className={`font-semibold ${dom.status.includes('FAILOVER') ? 'text-primary' : 'text-emerald-500'}`}>{dom.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

      </section>

      {/* Monitored Repos and Link Ingestions */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Monitored Links Ingestion table */}
        <div className="lg:col-span-2 premium-card flex flex-col gap-4 font-mono">
          <div className="flex justify-between items-center border-b border-border/60 pb-3">
            <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Live Telemetry Ingestions</h4>

            {/* Form */}
            <form onSubmit={handleIngest} className="flex gap-2">
              <input
                type="text"
                placeholder="https://github.com/org/repo"
                className="bg-background text-xs px-4 py-2.5 rounded-xl border border-border outline-none focus:border-primary placeholder-muted-foreground w-56 font-mono shadow-sm"
                value={newLink}
                onChange={(e) => setNewLink(e.target.value)}
              />
              <button
                type="submit"
                disabled={ingestMutation.isPending}
                className="bg-primary hover:opacity-90 text-primary-foreground text-xs px-5 py-2.5 rounded-xl font-sans font-bold flex items-center gap-1.5 shrink-0 shadow-sm cursor-pointer border border-primary/20 active:scale-[0.98] transition-all"
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </form>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-[10px] divide-y divide-border">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="pb-2 font-medium">Service name</th>
                  <th className="pb-2 font-medium">Domain</th>
                  <th className="pb-2 font-medium">Uptime</th>
                  <th className="pb-2 font-medium">Errors (24h)</th>
                  <th className="pb-2 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {monitoring.map((item, idx) => (
                  <tr key={idx} className="group hover:bg-secondary/20">
                    <td className="py-2.5 font-semibold text-foreground flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${item.status === 'CONNECTED' ? 'bg-emerald-500' : (item.status === 'DEGRADED' ? 'bg-amber-500' : 'bg-rose-500')}`} />
                      {item.name}
                    </td>
                    <td className="py-2.5 text-muted-foreground max-w-[120px] truncate">{item.domain}</td>
                    <td className="py-2.5">{item.uptime_percent}%</td>
                    <td className="py-2.5 text-rose-500">{item.errors_24h}</td>
                    <td className="py-2.5 text-right">
                      {item.url.startsWith('http') && item.name !== 'BLACKHOLE' && item.name !== 'UNI_GURU' ? (
                        <button
                          onClick={() => handleRemove(item.url)}
                          className="p-1 hover:text-rose-500 text-muted-foreground transition-colors"
                          title="Remove from monitoring"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <span className="text-[9px] text-muted-foreground italic">System Core</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live System Events feed */}
        <div className="premium-card flex flex-col gap-4 font-mono">
          <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Ecosystem Timeline Events</h4>
          <div className="flex flex-col gap-3 py-1 overflow-y-auto max-h-[300px]">
            {eventsData?.events && eventsData.events.length > 0 ? (
              eventsData.events.map((ev, i) => (
                <div key={i} className="flex gap-2.5 items-start text-[10px] leading-relaxed border-l-2 border-border pl-3.5 py-0.5">
                  <div className="flex-1 flex flex-col gap-0.5">
                    <div className="flex items-center justify-between">
                      <span className="text-foreground font-semibold uppercase">{ev.service}</span>
                      <span className={`text-[9px] font-mono ${ev.status === 'healthy' ? 'text-emerald-500' : 'text-amber-500'}`}>
                        {ev.status} {ev.latency_ms ? `(${Math.round(ev.latency_ms)}ms)` : ''}
                      </span>
                    </div>
                    <span className="text-[9px] text-muted-foreground truncate max-w-xs">{ev.sanitized_detail || ev.detail}</span>
                    <span className="text-[8px] text-muted-foreground/60">{ev.ts ? new Date(ev.ts).toLocaleTimeString() : ''}</span>
                  </div>
                </div>
              ))
            ) : Array.isArray(dashboard.live_events) && dashboard.live_events.length > 0 ? (
              dashboard.live_events.map((ev, i) => (
                <div key={i} className="flex gap-2.5 items-start text-[10px] leading-relaxed border-l-2 border-border pl-3.5 py-0.5">
                  <div className="flex-1 flex flex-col gap-0.5">
                    <span className="text-foreground font-medium">{ev.title}</span>
                    <span className="text-[9px] text-muted-foreground">{ev.time_ago}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-muted-foreground italic py-4 text-center">
                No observer timeline events recorded.
              </div>
            )}
          </div>
        </div>

      </section>

    </div>
  );
}
