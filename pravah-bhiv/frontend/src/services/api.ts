import axios from 'axios';
import {
  LiveDashboardResponse,
  AutonomousStatus,
  Decision,
  EvidenceBundle,
  ObservedService,
  TelemetryEvent,
  ActionScope,
  RuntimeState,
  UnifiedProductHealthResponse,
  TrafficSummary,
  PerformanceSummary,
  DependencyNode,
  IncidentItem
} from '../types';

const DECISION_BRAIN_URL = process.env.NEXT_PUBLIC_DECISION_BRAIN_URL || 'http://localhost:8010';
const CONTROL_PLANE_URL = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL || 'http://localhost:7000';
const OBSERVER_URL = process.env.NEXT_PUBLIC_OBSERVER_URL || 'http://localhost:8600';

// Axios clients
export const decisionBrainApi = axios.create({
  baseURL: DECISION_BRAIN_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const controlPlaneApi = axios.create({
  baseURL: CONTROL_PLANE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const observerApi = axios.create({
  baseURL: OBSERVER_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API Functions
export const api = {
  // === DECISION BRAIN ENDPOINTS (Port 8000) ===
  getLiveDashboard: async (): Promise<LiveDashboardResponse> => {
    const res = await decisionBrainApi.get<LiveDashboardResponse>('/live-dashboard');
    return res.data;
  },

  getAutonomousStatus: async (): Promise<AutonomousStatus> => {
    const res = await decisionBrainApi.get<AutonomousStatus>('/autonomous-status');
    return res.data;
  },

  getRecentActivity: async (): Promise<{ items: Decision[] }> => {
    const res = await decisionBrainApi.get<{ items: Decision[] }>('/recent-activity');
    return res.data;
  },

  getDecisionSummary: async (): Promise<{
    total_decisions: number;
    last_action: string;
    success_rate: number;
    demo_frozen: boolean;
    stateless: boolean;
  }> => {
    const res = await decisionBrainApi.get('/decision-summary');
    return res.data;
  },

  getActionScope: async (): Promise<ActionScope> => {
    const res = await decisionBrainApi.get<ActionScope>('/action-scope');
    return res.data;
  },

  getOrchestrationMetrics: async (): Promise<{
    rl_brain: Record<string, any>;
    control_plane: Record<string, any>;
    unified: Record<string, any>;
  }> => {
    const res = await decisionBrainApi.get('/orchestration/metrics');
    return res.data;
  },

  getLineageReplay: async (
    executionId: string,
    params?: { state?: string; start_ts?: number; end_ts?: number }
  ): Promise<{
    execution_id: string;
    valid: boolean;
    final_state: string | null;
    execution_state_history: string[];
    events: any[];
    execution_hash: string | null;
    runtime_attestation: Record<string, any> | null;
  }> => {
    const res = await decisionBrainApi.get(`/api/lineage/${executionId}`, { params });
    return res.data;
  },

  verifyLineage: async (executionId: string): Promise<{
    execution_id: string;
    valid: boolean;
    hash_chain_valid: boolean;
    fsm_valid: boolean;
    error: string | null;
    runtime_attestation_valid: boolean | null;
    runtime_attestation_error: string | null;
  }> => {
    const res = await decisionBrainApi.get(`/api/lineage/${executionId}/verify`);
    return res.data;
  },

  ingestLink: async (link: string): Promise<{ success: boolean; message?: string; error?: string; ingested_link?: any }> => {
    const res = await axios.post('/api/ingest-link', { link });
    return res.data;
  },

  removeLink: async (link: string): Promise<{ success: boolean; message?: string; error?: string }> => {
    const res = await axios.post('/api/remove-link', { link });
    return res.data;
  },

  // === CONTROL PLANE ENDPOINTS (Port 7000) ===
  getAppRegistry: async (): Promise<{ status: string; apps: string[] }> => {
    const res = await controlPlaneApi.get<{ status: string; apps: string[] }>('/api/control-plane/apps');
    return res.data;
  },

  getHealthOverview: async (): Promise<{ status: string; overview: Record<string, any> }> => {
    const res = await controlPlaneApi.get<{ status: string; overview: Record<string, any> }>('/api/control-plane/health');
    return res.data;
  },

  getDecisionHistory: async (appName: string, limit = 50): Promise<{ status: string; app_name: string; timeline: Decision[] }> => {
    const res = await controlPlaneApi.get<{ status: string; app_name: string; timeline: Decision[] }>(
      `/api/control-plane/history/${appName}`,
      { params: { limit } }
    );
    return res.data;
  },

  postOverride: async (payload: {
    app_name: string;
    action: 'freeze' | 'clear_freeze' | 'set_freeze';
    duration?: number;
    duration_minutes?: number;
    reason?: string;
  }): Promise<{ status: string; result: any }> => {
    const res = await controlPlaneApi.post<{ status: string; result: any }>('/api/control-plane/override', payload);
    return res.data;
  },

  getUnifiedRegistryTrace: async (traceId: string): Promise<any> => {
    const res = await controlPlaneApi.get(`/registry/trace/${traceId}`);
    return res.data;
  },

  // === OBSERVER ENDPOINTS (Port 8600) ===
  getObserverStatus: async (): Promise<{
    started_at: string;
    poll_count: number;
    services: Record<string, ObservedService>;
  }> => {
    const res = await observerApi.get('/api/status');
    return res.data;
  },

  getObserverEvents: async (limit = 100): Promise<{
    events: TelemetryEvent[];
    total: number;
  }> => {
    const res = await observerApi.get('/api/events', { params: { limit } });
    return res.data;
  },

  getObserverLineage: async (): Promise<{
    lineages: EvidenceBundle[];
  }> => {
    const res = await observerApi.get('/api/lineage');
    return res.data;
  },

  getUnifiedProductHealth: async (): Promise<UnifiedProductHealthResponse> => {
    const res = await observerApi.get<UnifiedProductHealthResponse>('/api/products/unified-health');
    return res.data;
  },

  getTrafficMetrics: async (): Promise<TrafficSummary> => {
    const res = await observerApi.get<TrafficSummary>('/api/metrics/traffic');
    return res.data;
  },

  getPerformanceMetrics: async (): Promise<PerformanceSummary> => {
    const res = await observerApi.get<PerformanceSummary>('/api/metrics/performance');
    return res.data;
  },

  getDependencyTopology: async (): Promise<{ topology: DependencyNode[]; count: number }> => {
    const res = await observerApi.get<{ topology: DependencyNode[]; count: number }>('/api/dependencies/graph');
    return res.data;
  },

  getIncidents: async (): Promise<{ incidents: IncidentItem[]; total: number }> => {
    const res = await observerApi.get<{ incidents: IncidentItem[]; total: number }>('/api/incidents');
    return res.data;
  },
};

// =============================================================================
// VANA API — Group 1 → Group 2 → Group 4 Live Pipeline
// =============================================================================

import type {
  VanaGroup1Response,
  VanaGroup2Ruling,
  VanaGovernedOutcome,
} from '../types';

// Group 1 — VANA MasterDB Observation API (live, port 8013)
const GROUP1_URL =
  process.env.NEXT_PUBLIC_VANA_GROUP1_URL || 'http://localhost:8013';

// Group 4 — deployed Decision Brain (port 8010 externally, same origin locally via /vana/execute)
const GROUP4_VANA_URL =
  process.env.NEXT_PUBLIC_VANA_GROUP4_URL || 'http://localhost:8010';

/**
 * Fetch a canonical observation from the Group 1 live API.
 * Throws on network failure or non-200 response.
 */
export async function fetchVanaObservation(
  observationId: string
): Promise<VanaGroup1Response> {
  const res = await fetch(`${GROUP1_URL}/observations/${encodeURIComponent(observationId)}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Group 1 responded ${res.status} for observation ${observationId}`);
  }
  const data: VanaGroup1Response = await res.json();
  if (data.status === 'NOT_FOUND') {
    throw new Error(`Observation ${observationId} not found in Group 1`);
  }
  return data;
}

// Group 2 — Proxy via Next.js to bypass CORS
const GROUP2_URL = '/api/vana/group2';

/**
 * Fetch the Group 2 ruling by sending the canonical observation.
 */
export async function fetchGroup2Ruling(
  group1Response: VanaGroup1Response
): Promise<VanaGroup2Ruling> {
  const res = await fetch(GROUP2_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(group1Response.observation), // Group 2 likely expects the observation object
  });

  if (!res.ok) {
    let errorText = '';
    try {
      const data = await res.json();
      errorText = data.error || JSON.stringify(data);
    } catch {
      errorText = await res.text().catch(() => '');
    }
    throw new Error(`Group 2 responded ${res.status}: ${errorText}`);
  }

  return res.json() as Promise<VanaGroup2Ruling>;
}

// Group 4 — Proxy via Next.js to bypass CORS
const GROUP4_PROXY_URL = '/api/vana/group4';

/**
 * Submit the Group 2 ruling to Group 4 POST /vana/execute.
 * Uses the proxy to bypass CORS restrictions.
 */
export async function submitVanaExecute(
  ruling: VanaGroup2Ruling
): Promise<VanaGovernedOutcome> {
  const res = await fetch(GROUP4_PROXY_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(ruling),
  });
  if (!res.ok) {
    let errorText = '';
    try {
      const data = await res.json();
      errorText = data.error || JSON.stringify(data);
    } catch {
      errorText = await res.text().catch(() => '');
    }
    throw new Error(`Group 4 responded ${res.status}: ${errorText}`);
  }
  return res.json() as Promise<VanaGovernedOutcome>;
}
