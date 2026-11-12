'use client';

import React from 'react';
import { useLiveDashboard, useTrafficMetrics, usePerformanceMetrics } from '../../hooks/useBackend';
import { 
  BarChart3, 
  Activity, 
  TrendingUp, 
  AlertOctagon, 
  DollarSign,
  Loader2,
  Clock,
  Gauge,
  Flame,
  CheckCircle2
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid, 
  LineChart, 
  Line 
} from 'recharts';

export default function Analytics() {
  const { data: dashboard, isLoading: dashLoading } = useLiveDashboard();
  const { data: trafficData, isLoading: trafficLoading } = useTrafficMetrics();
  const { data: perfData, isLoading: perfLoading } = usePerformanceMetrics();

  if (dashLoading || trafficLoading || perfLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 py-20 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-xs text-muted-foreground font-mono">CALCULATING ECOSYSTEM ANALYTICS...</span>
      </div>
    );
  }

  const runtimes = dashboard?.monitored_services || dashboard?.live_production_monitoring || [];

  const statusCodeData = [
    { code: '2xx OK', count: trafficData?.success_2xx || 0, fill: '#10b981' },
    { code: '3xx Redirect', count: trafficData?.redirect_3xx || 0, fill: '#3b82f6' },
    { code: '4xx Client Err', count: trafficData?.client_error_4xx || 0, fill: '#f59e0b' },
    { code: '5xx Server Err', count: trafficData?.server_error_5xx || 0, fill: '#ef4444' },
  ];

  const slowEndpoints = perfData?.slow_endpoints || [];

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary" />
            Performance & Traffic Analytics
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5 font-sans">
            Sliding-window request rates (RPS), HTTP status distribution, exact P50/P95/P99 latency percentiles, and SLA tracking.
          </p>
        </div>
      </header>

      {/* Requirement 3 & 4: Application Traffic vs Background Health Probes */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-primary" />
            1. Application Request Telemetry (End-User & API Traffic)
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${trafficData?.has_application_traffic ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-secondary text-muted-foreground'}`}>
            {trafficData?.has_application_traffic ? 'LIVE INGESTION ACTIVE' : 'NO SAMPLES RECORDED'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* App RPS */}
          <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Application RPS (1m / 5m / 1h)</span>
            <div className="flex items-baseline gap-2 font-sans">
              <span className="text-xl font-bold text-foreground">
                {trafficData?.has_application_traffic ? `${trafficData.rps_1m.toFixed(2)}` : '0.00'}
              </span>
              <span className="text-xs text-muted-foreground">
                / {trafficData?.has_application_traffic ? trafficData.rps_5m.toFixed(2) : '0.00'} / {trafficData?.has_application_traffic ? trafficData.rps_1h.toFixed(2) : '0.00'} RPS
              </span>
            </div>
            <div className="absolute right-3 top-3 opacity-10">
              <Gauge className="w-8 h-8 text-primary" />
            </div>
          </div>

          {/* App Error Rate */}
          <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Application Error Rate</span>
            <span className={`text-xl font-bold font-sans ${trafficData?.has_application_traffic ? ((trafficData.error_rate_pct || 0) > 1.0 ? 'text-rose-400' : 'text-emerald-400') : 'text-muted-foreground'}`}>
              {trafficData?.has_application_traffic ? `${trafficData.error_rate_pct.toFixed(2)}%` : '0.00%'}
            </span>
            <div className="absolute right-3 top-3 opacity-10">
              <Flame className="w-8 h-8 text-rose-500" />
            </div>
          </div>

          {/* App Latency */}
          <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Application Latency (P95)</span>
            <div className="flex items-baseline gap-2 font-sans">
              <span className="text-xl font-bold text-foreground">
                {perfData?.has_application_data && perfData.overall_p95_ms !== null ? `${perfData.overall_p95_ms}ms` : 'N/A'}
              </span>
              <span className="text-xs text-muted-foreground font-mono">
                {perfData?.has_application_data ? `(p50: ${perfData.overall_p50_ms ?? '0'}ms, p99: ${perfData.overall_p99_ms ?? '0'}ms)` : '(Awaiting user requests)'}
              </span>
            </div>
            <div className="absolute right-3 top-3 opacity-10">
              <Clock className="w-8 h-8 text-primary" />
            </div>
          </div>

          {/* App Total Calls */}
          <div className="premium-card flex flex-col gap-1 relative overflow-hidden">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Application Total Requests</span>
            <span className="text-xl font-bold text-foreground font-sans">
              {trafficData?.has_application_traffic ? trafficData.total_requests.toLocaleString() : '0'}
            </span>
            <div className="absolute right-3 top-3 opacity-10">
              <TrendingUp className="w-8 h-8 text-primary" />
            </div>
          </div>
        </div>
      </section>

      {/* 2. Automated Observer Health Probes (Isolated) */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-blue-400" />
            2. Observer Health Check Probes (Ecosystem Socket Probes)
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/40">
            POLLING (10s INTERVAL)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="premium-card flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Probe Execution Rate</span>
            <span className="text-lg font-bold font-sans text-foreground">
              {trafficData?.probe_rps_1m !== undefined ? `${trafficData.probe_rps_1m.toFixed(2)} RPS` : (trafficData ? `${trafficData.rps_1m.toFixed(2)} RPS` : '0.00 RPS')}
            </span>
            <span className="text-[10px] text-muted-foreground">Automated socket heartbeat loop</span>
          </div>

          <div className="premium-card flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">External Unreachable Rate</span>
            <span className="text-lg font-bold font-sans text-rose-400">
              {trafficData?.probe_error_rate_pct !== undefined ? `${trafficData.probe_error_rate_pct.toFixed(1)}%` : (trafficData ? `${trafficData.error_rate_pct.toFixed(1)}%` : '0.0%')}
            </span>
            <span className="text-[10px] text-muted-foreground">23 unhosted cloud endpoints</span>
          </div>

          <div className="premium-card flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Socket Probe P95 Latency</span>
            <span className="text-lg font-bold font-sans text-foreground">
              {perfData?.probe_p95_ms !== undefined && perfData?.probe_p95_ms !== null ? `${perfData.probe_p95_ms}ms` : (perfData?.overall_p95_ms ? `${perfData.overall_p95_ms}ms` : 'N/A')}
            </span>
            <span className="text-[10px] text-muted-foreground">Includes 8.0s TCP timeouts</span>
          </div>

          <div className="premium-card flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Health Probes</span>
            <span className="text-lg font-bold font-sans text-foreground">
              {trafficData?.probe_total_requests !== undefined ? trafficData.probe_total_requests.toLocaleString() : (trafficData?.total_requests?.toLocaleString() || '0')}
            </span>
            <span className="text-[10px] text-muted-foreground">Cumulative socket probes</span>
          </div>
        </div>
      </section>

      {/* Traffic & Status Codes Charts */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Code Distribution Bar Chart */}
        <div className="premium-card flex flex-col gap-4">
          <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">HTTP Status Distribution (2xx / 3xx / 4xx / 5xx)</h4>
          <div className="h-56 w-full text-[10px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusCodeData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="code" stroke="var(--muted-foreground)" />
                <YAxis stroke="var(--muted-foreground)" />
                <Tooltip contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)' }} />
                <Bar dataKey="count" name="Total Responses" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* SLA Slow Endpoints Table */}
        <div className="premium-card flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/40 pb-2">
            <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">SLA Threshold Violations (&gt; 2000ms)</h4>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary/60 border border-border/50 text-muted-foreground whitespace-nowrap">
              {slowEndpoints.length} flagged
            </span>
          </div>
          <div className="overflow-x-auto max-h-56">
            <table className="w-full text-left text-[10px] divide-y divide-border">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="pb-2 font-medium">Service / Endpoint</th>
                  <th className="pb-2 font-medium">Latency (P95)</th>
                  <th className="pb-2 font-medium">SLA Threshold</th>
                  <th className="pb-2 font-medium text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {slowEndpoints.length > 0 ? (
                  slowEndpoints.map((ep, i) => (
                    <tr key={i} className="hover:bg-secondary/20">
                      <td className="py-2 text-foreground font-semibold uppercase">{ep.service}</td>
                      <td className="py-2 text-rose-400 font-bold">{ep.p95_ms} ms</td>
                      <td className="py-2 text-muted-foreground">{ep.sla_ms} ms</td>
                      <td className="py-2 text-right">
                        <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-300 border border-rose-500/40 rounded text-[9px] font-bold">BREACH</span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-muted-foreground italic">
                      All monitored services within SLA bounds.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

    </div>
  );
}
