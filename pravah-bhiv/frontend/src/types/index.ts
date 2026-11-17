export interface ObservedService {
  url: string;
  status: 'healthy' | 'degraded' | 'unreachable' | 'timeout' | 'error';
  latency_ms: number;
  detail: string;
  last_checked: string;
  name?: string;
  canonical_state?: string;
  consecutive_failures?: number;
  failure_reason?: string | null;
  failure_category?: string;
  last_successful_check?: string | null;
}

export interface TelemetryEvent {
  ts: string;
  service: string;
  status: string;
  detail: string;
  latency_ms: number;
  http_status?: number | null;
  failure_category?: string;
  sanitized_detail?: string;
}

export interface EvidenceBundle {
  bundle_id: string;
  trace_id: string;
  execution_id: string;
  decision_id: string;
  decision_type: string;
  authority_chain: string[];
  evidence: Record<string, any> | Record<string, any>[];
  replay_reference?: string;
  constitutional_hash?: string;
  produced_at: string;
  correlation_id?: string;
  source?: string;
  action?: string;
}

export interface Decision {
  decision_id?: string;
  decision_type?: string;
  environment?: string;
  selected_action?: string;
  action?: string;
  reason: string;
  confidence?: number;
  timestamp?: string;
  version?: string;
  app_name?: string;
  executed_action?: string;
  execution_success?: boolean;
  event?: {
    trace_id: string;
    correlation_id: string;
  };
}

export interface RuntimeMetrics {
  cpu: number;
  memory: number;
  error_rate: number;
  uptime: number;
  workers?: number;
}

export interface RuntimeState {
  service_id: string;
  timestamp: string;
  status: string;
  metrics: RuntimeMetrics;
  issue_detected: boolean;
  issue_type: string;
  recommended_action: string;
}

export interface LiveProductionMonitoredService {
  name: string;
  domain: string;
  url: string;
  status: 'CONNECTED' | 'DEGRADED' | 'DISCONNECTED' | 'CRITICAL' | 'HEALTHY' | string;
  health_score: number;
  response_time_ms: number;
  cpu_percent: number | null;
  memory_percent: number | null;
  uptime_percent: number;
  last_action: string;
  errors_24h: number;
}

export interface FileStatusRow {
  filename: string;
  status: 'ACTIVE' | 'MISSING';
  size: string;
}

export interface ProjectFileSection {
  title: string;
  icon: string;
  active: number;
  total: number;
  files: FileStatusRow[];
}

export interface SystemHealthObject {
  cpu_utilization_pct: number | null;
  memory_utilization_pct: number | null;
  status: string;
  collection_status: string;
}

export interface LiveDashboardResponse {
  generated_at: string;
  environment?: string;
  monitored_services?: LiveProductionMonitoredService[];
  system_health?: SystemHealthObject | { label: string; value: string; tone?: string }[];
  ml_intelligence?: Record<string, any>;
  recent_decisions?: Decision[];
  header?: {
    title: string;
    subtitle: string;
  };
  live_production_monitoring?: LiveProductionMonitoredService[];
  summary_metrics?: { label: string; value: string }[];
  ai_learning_status?: { label: string; value: string; tone: string }[];
  performance_metrics?: { label: string; value: string }[];
  project_files_status?: ProjectFileSection[];
  enhanced_telemetry?: {
    status: string;
    avg_latency: string;
    cost: string;
    success: string;
    requests: string;
  };
  policy_evolution?: {
    title: string;
    metrics: { label: string; value: string }[];
  };
  error_analytics?: {
    recent_errors: { code: string; severity: string }[];
    statistics: {
      total_errors: number;
      avg_impact_score: number;
      critical_issues: number;
      test_coverage_avg: number;
    };
  };
  auto_failover_status?: {
    active_domain: string;
    failure_threshold: number;
    domains: { name: string; status: string }[];
  };
  live_events?: { title: string; time_ago: string; tone: string }[];
}

export interface AutonomousStatus {
  last_runtime: Record<string, any> | null;
  last_action: string | null;
  recent_autonomous_decisions: Record<string, any>[];
  loop_running: boolean;
}

export interface ActionScope {
  [environment: string]: string[];
}

// =============================================================================
// VANA Types — Group 1 → Group 2 → Group 4 Lineage
// =============================================================================

/** Raw artifact integrity from Group 1 */
export interface VanaRawArtifactIntegrity {
  checksum_sha256: string;
  hash_algorithm: string;
  artifact_type: string;
}

/** A single measurement from a Group 1 observation */
export interface VanaMeasurement {
  measurement_id: string;
  metric_name: string;
  data_type: string;
  value: number | null;
  value_text: string | null;
  unit: string;
  method: string;
}

/** Full canonical observation returned by Group 1 GET /observations/{id} */
export interface VanaObservation {
  observation_id: string;
  canonical_record_id: string;
  dataset_id: string;
  geo_id: string;
  observed_at: string;
  observation_timestamp: string;
  observation_type: string;
  quality_status: string;
  data_state: string;
  is_synthetic: boolean;
  capture_method: string;
  device_id: string;
  provenance_reference: string;
  latitude: number;
  longitude: number;
  altitude_m: number | null;
  gnss_status: string;
  calibration_status: string;
  measurements: VanaMeasurement[];
  raw_artifact: string;
  raw_artifact_integrity: VanaRawArtifactIntegrity;
  geo_location?: {
    place_name: string;
    latitude: number;
    longitude: number;
    altitude_m: number | null;
    crs: string;
  };
  field_observation_meta?: {
    device_id: string;
    operator: string;
    mission_id: string;
    processing_status: string;
    calibration_status: string;
    gnss_status: string;
    notes: string | null;
  };
}

/** Group 1 API response envelope */
export interface VanaGroup1Response {
  trace_id: string;
  observation_id: string;
  status: 'RETRIEVED' | 'NOT_FOUND' | string;
  observation: VanaObservation;
}

/** The payload sent to Group 4 POST /vana/execute (mirrors Group 2 ruling) */
export interface VanaGroup2Ruling {
  observation_id: string;
  canonical_record_id: string;
  context_id: string | null;
  ruling: 'ABSTAIN' | 'ALLOW' | 'DENY' | 'BLOCK';
  action_eligibility: boolean;
  abstention_required: boolean;
  action_request: null | Record<string, unknown>;
  evidence: {
    source: string;
    confidence?: string;
    missing_critical_data?: string;
    provenance_reference?: string;
    artifact_hash?: string;
    artifact_type?: string;
    observation_timestamp?: string;
    retrieval_timestamp?: string;
    attribution?: string;
    canonical_observation_location?: string;
    [key: string]: unknown;
  };
  provenance?: {
    group2_decision_time?: string;
    reason?: string;
    message?: string;
    [key: string]: unknown;
  };
}

/** Evidence block inside Group 4 response */
export interface VanaGovernedEvidence {
  event_type: string;
  abstention_record_id: string;
  event_id: string;
  execution_id: string;
  observation_id: string;
  context_id: string | null;
  ruling: string;
  decision_action: string;
  governance_allowed: boolean;
  recorded_at: string;
  canonical_record_id: string;
}

/** Full Group 4 response from POST /vana/execute */
export interface VanaGovernedOutcome {
  status: 'governed_abstention' | 'action_request_generated' | string;
  evidence: VanaGovernedEvidence;
}

/** Execution status derived from governance outcome */
export type VanaExecutionStatus =
  | 'NOT_EXECUTED'
  | 'EXECUTED'
  | 'GOVERNED_ABSTENTION'
  | 'ACTION_REQUEST_GENERATED';

/** Single pipeline stage status */
export type VanaStageStatus = 'idle' | 'loading' | 'success' | 'error' | 'unavailable';

/** Full VANA lineage pipeline state held in component */
export interface VanaLineagePipelineState {
  selectedObservationId: string | null;
  group1Status: VanaStageStatus;
  group1Response: VanaGroup1Response | null;
  group1Error: string | null;
  group2Status: VanaStageStatus;
  group2Ruling: VanaGroup2Ruling | null;
  group2Error: string | null;
  group4Status: VanaStageStatus;
  group4Outcome: VanaGovernedOutcome | null;
  group4Error: string | null;
}

/** Known region / observation IDs for the selector */
export interface VanaRegion {
  label: string;
  observation_id: string;
  description: string;
  available: boolean;
}


// =============================================================================
// Product Health & Observability Types (Requirements 1-7)
// =============================================================================

export type CanonicalServiceState = 'Healthy' | 'Degraded' | 'Unreachable' | 'Stale' | 'Not Monitored';

export interface UnifiedProductItem {
  name: string;
  url: string;
  status: CanonicalServiceState;
  tier: 'product' | 'platform';
  consecutive_failures: number;
  last_successful_check: string | null;
  last_checked: string | null;
  failure_reason: string | null;
  failure_category: string;
  failure_duration_seconds: number;
  http_status: number | null;
  latency_p95_ms: number | null;
  latency_avg_ms: number | null;
  dependencies: string[];
}

export interface UnifiedProductHealthResponse {
  timestamp: string;
  products: UnifiedProductItem[];
  platform_health: {
    status: 'Healthy' | 'Degraded' | 'Unreachable';
    services: UnifiedProductItem[];
  };
  traffic: TrafficSummary;
  performance: PerformanceSummary;
  active_incidents: IncidentItem[];
  all_incidents: IncidentItem[];
}

export interface TrafficSummary {
  total_requests: number;
  success_2xx: number;
  redirect_3xx: number;
  client_error_4xx: number;
  server_error_5xx: number;
  error_rate_pct: number;
  rps_1m: number;
  rps_5m: number;
  rps_1h: number;
  hourly_trend: Array<{ hour: string; total: number; errors: number }>;
  has_application_traffic?: boolean;
  probe_total_requests?: number;
  probe_rps_1m?: number;
  probe_rps_5m?: number;
  probe_rps_1h?: number;
  probe_error_rate_pct?: number;
  sources?: {
    application: Record<string, any>;
    probe: Record<string, any>;
    agent: Record<string, any>;
    synthetic: Record<string, any>;
  };
}

export interface PerformanceSummary {
  overall_avg_ms: number | null;
  overall_p50_ms: number | null;
  overall_p95_ms: number | null;
  overall_p99_ms: number | null;
  total_samples: number;
  timeout_count: number;
  has_application_data?: boolean;
  probe_p50_ms?: number | null;
  probe_p95_ms?: number | null;
  probe_p99_ms?: number | null;
  probe_timeout_count?: number;
  probe_total_samples?: number;
  slow_endpoints: Array<{
    service: string;
    p95_ms: number;
    avg_ms: number | null;
    sla_ms: number;
    type?: string;
  }>;
  sources?: {
    application: Record<string, any>;
    probe: Record<string, any>;
    agent: Record<string, any>;
    synthetic: Record<string, any>;
  };
}

export interface DependencyNode {
  service: string;
  product: string;
  tier: 'product' | 'platform';
  dependencies: Array<{
    dependency: string;
    status: CanonicalServiceState | string;
    last_checked: string | null;
  }>;
}

export interface IncidentItem {
  incident_id: string;
  started_at: string;
  last_updated: string;
  status: 'ACTIVE' | 'RESOLVED';
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  symptoms: string[];
  affected_products: string[];
  probable_source: string;
  resolution: string | null;
}
