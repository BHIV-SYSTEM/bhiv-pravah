'use client';

import React, { useCallback, useReducer } from 'react';
import {
  Leaf, MapPin, Database, Brain, ShieldCheck, GitBranch, RefreshCw,
  ChevronDown, Loader2, Activity, Hash, Eye, Info, CheckCircle2, XCircle, Clock, AlertTriangle, ShieldAlert
} from 'lucide-react';
import {
  fetchVanaObservation, fetchGroup2Ruling, submitVanaExecute,
} from '../../services/api';
import type {
  VanaLineagePipelineState, VanaRegion, VanaGroup1Response, VanaGroup2Ruling,
  VanaGovernedOutcome, VanaStageStatus,
} from '../../types';

const VANA_REGIONS: VanaRegion[] = [
  { label: 'Zone 3 — Open-Meteo Precipitation (TC-Z03)', observation_id: 'TC-Z03-EXT-OPENMETEO-OBS001', description: 'Mangrove site, 19.1288°N 72.9421°E — External precipitation sensor reading via Open-Meteo.com live API.', available: true },
  { label: 'Zone 1 — LiDAR Canopy Survey (TC-Z01)', observation_id: 'TC-Z01-LIDAR-OBS001', description: 'LiDAR canopy height measurement — VM deployment pending.', available: false },
  { label: 'Zone 2 — Soil Moisture (TC-Z02)', observation_id: 'TC-Z02-SOIL-OBS001', description: 'In-situ soil moisture sensor — live endpoint not yet available.', available: false },
  { label: 'Zone 4 — Tidal Gauge (TC-Z04)', observation_id: 'TC-Z04-TIDAL-OBS001', description: 'Coastal tidal gauge reading — integration pending.', available: false },
  { label: 'Zone 5 — Drone NDVI (TC-Z05)', observation_id: 'TC-Z05-DRONE-OBS001', description: 'Drone multispectral NDVI — mission data pending.', available: false },
  { label: 'Zone 6 — Salinity Probe (TC-Z06)', observation_id: 'TC-Z06-SALINITY-OBS001', description: 'Estuarine salinity measurement — VM deployment pending.', available: false },
];

type PipelineAction =
  | { type: 'SELECT_REGION'; observationId: string }
  | { type: 'GROUP1_LOADING' } | { type: 'GROUP1_SUCCESS'; response: VanaGroup1Response } | { type: 'GROUP1_ERROR'; error: string }
  | { type: 'GROUP2_LOADING' } | { type: 'GROUP2_SUCCESS'; ruling: VanaGroup2Ruling } | { type: 'GROUP2_ERROR'; error: string }
  | { type: 'GROUP4_LOADING' } | { type: 'GROUP4_SUCCESS'; outcome: VanaGovernedOutcome } | { type: 'GROUP4_ERROR'; error: string }
  | { type: 'RESET' };

const initialState: VanaLineagePipelineState = {
  selectedObservationId: null, group1Status: 'idle', group1Response: null, group1Error: null,
  group2Status: 'idle', group2Ruling: null, group2Error: null,
  group4Status: 'idle', group4Outcome: null, group4Error: null,
};

function pipelineReducer(state: VanaLineagePipelineState, action: PipelineAction): VanaLineagePipelineState {
  switch (action.type) {
    case 'SELECT_REGION': return { ...initialState, selectedObservationId: action.observationId };
    case 'RESET': return initialState;
    case 'GROUP1_LOADING': return { ...state, group1Status: 'loading', group1Response: null, group1Error: null };
    case 'GROUP1_SUCCESS': return { ...state, group1Status: 'success', group1Response: action.response };
    case 'GROUP1_ERROR': return { ...state, group1Status: 'error', group1Error: action.error };
    case 'GROUP2_LOADING': return { ...state, group2Status: 'loading', group2Ruling: null, group2Error: null };
    case 'GROUP2_SUCCESS': return { ...state, group2Status: 'success', group2Ruling: action.ruling };
    case 'GROUP2_ERROR': return { ...state, group2Status: 'error', group2Error: action.error };
    case 'GROUP4_LOADING': return { ...state, group4Status: 'loading', group4Outcome: null, group4Error: null };
    case 'GROUP4_SUCCESS': return { ...state, group4Status: 'success', group4Outcome: action.outcome };
    case 'GROUP4_ERROR': return { ...state, group4Status: 'error', group4Error: action.error };
    default: return state;
  }
}

function stageColor(status: VanaStageStatus): string {
  switch (status) {
    case 'success': return 'text-emerald-500 border-emerald-500/30 bg-emerald-500/5';
    case 'loading': return 'text-amber-400 border-amber-400/30 bg-amber-400/5';
    case 'error': return 'text-rose-500 border-rose-500/30 bg-rose-500/5';
    case 'unavailable': return 'text-slate-500 border-slate-500/30 bg-slate-500/5';
    default: return 'text-muted-foreground border-border/40 bg-secondary/10';
  }
}

function StageIcon({ status }: { status: VanaStageStatus }) {
  switch (status) {
    case 'success': return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    case 'loading': return <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />;
    case 'error': return <XCircle className="w-4 h-4 text-rose-500" />;
    case 'unavailable': return <AlertTriangle className="w-4 h-4 text-slate-500" />;
    default: return <Clock className="w-4 h-4 text-muted-foreground" />;
  }
}

function StatusPill({ label, tone }: { label: string; tone: 'green' | 'amber' | 'red' | 'blue' | 'slate' }) {
  const colors = { green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20', red: 'bg-rose-500/10 text-rose-400 border-rose-500/20', blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20', slate: 'bg-slate-500/10 text-slate-400 border-slate-500/20' };
  return <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-bold font-mono uppercase ${colors[tone]}`}>{label}</span>;
}

function Field({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] text-muted-foreground uppercase tracking-wider">{label}</span>
      <span className={`text-[11px] text-foreground ${mono ? 'font-mono' : 'font-sans'} break-all`}>{value ?? <span className="text-muted-foreground italic">null</span>}</span>
    </div>
  );
}

function SectionCard({ icon, title, status, children }: { icon: React.ReactNode; title: string; status: VanaStageStatus; children?: React.ReactNode }) {
  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-3 transition-colors duration-300 ${stageColor(status)}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">{icon}<span className="font-bold text-xs uppercase tracking-wider">{title}</span></div>
        <StageIcon status={status} />
      </div>
      {children}
    </div>
  );
}

function LineageStep({ icon, label, value, sub, tone, isLast = false }: { icon: React.ReactNode; label: string; value: string; sub: string; tone: 'blue' | 'amber' | 'green' | 'red'; isLast?: boolean }) {
  const colors: Record<string, string> = { blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20', amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20', green: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', red: 'text-rose-400 bg-rose-500/10 border-rose-500/20' };
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center w-8 shrink-0">
        <div className={`flex items-center justify-center w-7 h-7 rounded-full border ${colors[tone]}`}>{icon}</div>
        {!isLast && <div className="w-px flex-1 bg-border/40 my-1" />}
      </div>
      <div className="flex flex-col gap-0.5 pb-4 flex-1 min-w-0">
        <span className="text-[9px] text-muted-foreground uppercase tracking-wider">{label}</span>
        <span className="text-[11px] text-foreground font-mono break-all">{value}</span>
        <span className="text-[9px] text-muted-foreground break-all">{sub}</span>
      </div>
    </div>
  );
}

export default function VanaControlCenter() {
  const [pipeline, dispatch] = useReducer(pipelineReducer, initialState);
  const [regionOpen, setRegionOpen] = React.useState(false);
  const [customId, setCustomId] = React.useState('');

  const runPipeline = useCallback(async (observationId: string) => {
    dispatch({ type: 'GROUP1_LOADING' });
    let g1Response: VanaGroup1Response;
    try {
      g1Response = await fetchVanaObservation(observationId);
      dispatch({ type: 'GROUP1_SUCCESS', response: g1Response });
    } catch (err) { dispatch({ type: 'GROUP1_ERROR', error: String(err) }); return; }

    dispatch({ type: 'GROUP2_LOADING' });
    let ruling: VanaGroup2Ruling;
    try {
      ruling = await fetchGroup2Ruling(g1Response);
      dispatch({ type: 'GROUP2_SUCCESS', ruling });
    } catch (err) { dispatch({ type: 'GROUP2_ERROR', error: String(err) }); return; }

    dispatch({ type: 'GROUP4_LOADING' });
    try {
      const outcome = await submitVanaExecute(ruling);
      dispatch({ type: 'GROUP4_SUCCESS', outcome });
    } catch (err) { dispatch({ type: 'GROUP4_ERROR', error: String(err) }); }
  }, []);

  const handleRegionSelect = useCallback((region: VanaRegion) => {
    if (!region.available) return;
    setRegionOpen(false);
    dispatch({ type: 'SELECT_REGION', observationId: region.observation_id });
    runPipeline(region.observation_id);
  }, [runPipeline]);

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = customId.trim();
    if (!id) return;
    dispatch({ type: 'SELECT_REGION', observationId: id });
    runPipeline(id);
  };

  const handleRefresh = () => {
    if (pipeline.selectedObservationId) {
      dispatch({ type: 'SELECT_REGION', observationId: pipeline.selectedObservationId });
      runPipeline(pipeline.selectedObservationId);
    }
  };

  const obs = pipeline.group1Response?.observation ?? null;
  const ruling = pipeline.group2Ruling ?? null;
  const outcome = pipeline.group4Outcome ?? null;
  const evidence = outcome?.evidence ?? null;

  const executionStatus: string = (() => {
    if (!evidence) return '—';
    if (evidence.ruling === 'ABSTAIN' && evidence.decision_action === 'noop') return 'NOT EXECUTED';
    if (outcome?.status === 'governed_abstention') return 'GOVERNED ABSTENTION';
    if (outcome?.status === 'action_request_generated') return 'EXECUTED';
    return outcome?.status ?? '—';
  })();

  const isPipelineRunning = ['loading'].includes(pipeline.group1Status) || ['loading'].includes(pipeline.group2Status) || ['loading'].includes(pipeline.group4Status);

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Leaf className="w-5 h-5 text-emerald-500" />
            VANA Control Center
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">Live Group 1 → Group 2 → Group 4 operational governance lineage</p>
        </div>
        <div className="flex items-center gap-2">
          {pipeline.selectedObservationId && (
            <button id="vana-refresh-btn" onClick={handleRefresh} disabled={isPipelineRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-lg text-[10px] font-bold transition-colors disabled:opacity-50">
              <RefreshCw className={`w-3 h-3 ${isPipelineRunning ? 'animate-spin' : ''}`} />REPLAY
            </button>
          )}
          <StatusPill label={pipeline.group4Status === 'success' ? executionStatus : pipeline.group4Status === 'loading' ? 'PROCESSING' : 'AWAITING INPUT'}
            tone={pipeline.group4Status === 'success' ? (executionStatus === 'NOT EXECUTED' ? 'amber' : 'green') : pipeline.group4Status === 'error' ? 'red' : 'slate'} />
        </div>
      </header>

      <section className="premium-card flex flex-col gap-4">
        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <MapPin className="w-4 h-4 text-emerald-500" />Observation Region / Selection
        </span>
        <div className="relative">
          <button id="vana-region-dropdown" onClick={() => setRegionOpen((v) => !v)}
            className="w-full flex items-center justify-between gap-2 px-3 py-2.5 bg-secondary/40 border border-border rounded-lg text-xs hover:border-primary/50 transition-colors">
            <span className="text-foreground truncate">
              {pipeline.selectedObservationId ? VANA_REGIONS.find((r) => r.observation_id === pipeline.selectedObservationId)?.label ?? `Custom: ${pipeline.selectedObservationId}` : 'Select an observation region…'}
            </span>
            <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground shrink-0 transition-transform ${regionOpen ? 'rotate-180' : ''}`} />
          </button>
          {regionOpen && (
            <div className="absolute z-50 top-full mt-1 w-full bg-card border border-border rounded-xl shadow-2xl overflow-hidden">
              {VANA_REGIONS.map((region) => (
                <button key={region.observation_id} id={`vana-region-${region.observation_id}`} onClick={() => handleRegionSelect(region)} disabled={!region.available}
                  className={`w-full flex flex-col gap-0.5 px-4 py-3 text-left transition-colors text-xs ${region.available ? 'hover:bg-primary/10 text-foreground cursor-pointer' : 'text-muted-foreground cursor-not-allowed opacity-50'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{region.label}</span>
                    {region.available ? <StatusPill label="LIVE" tone="green" /> : <StatusPill label="UNAVAILABLE" tone="slate" />}
                  </div>
                  <span className="text-[10px] text-muted-foreground">{region.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <form onSubmit={handleCustomSubmit} className="flex gap-2">
          <input id="vana-custom-obs-input" type="text" placeholder="Or enter custom observation_id…" value={customId}
            onChange={(e) => setCustomId(e.target.value)}
            className="flex-1 bg-secondary/40 border border-border rounded-lg px-3 py-2 outline-none focus:border-primary text-xs text-foreground" />
          <button id="vana-custom-obs-submit" type="submit" disabled={!customId.trim() || isPipelineRunning}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-[10px] font-bold hover:opacity-90 disabled:opacity-50 transition-opacity">
            RUN PIPELINE
          </button>
        </form>
      </section>

      {pipeline.selectedObservationId && (
        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground px-1">
            <span className="text-foreground font-bold uppercase">LIVE PIPELINE</span>
            <span>·</span>
            <span className="font-mono truncate">{pipeline.selectedObservationId}</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <SectionCard icon={<Database className="w-4 h-4 text-blue-400" />} title="Group 1 — Canonical Observation" status={pipeline.group1Status}>
              {pipeline.group1Status === 'idle' && <span className="text-[10px] text-muted-foreground italic">Awaiting observation retrieval…</span>}
              {pipeline.group1Status === 'loading' && <span className="text-[10px] text-muted-foreground">Fetching from VANA MasterDB…</span>}
              {pipeline.group1Status === 'error' && <div className="flex flex-col gap-1"><span className="text-[10px] text-rose-400 font-bold">GROUP 1 API ERROR</span><span className="text-[10px] text-rose-300 break-all">{pipeline.group1Error}</span></div>}
              {pipeline.group1Status === 'success' && obs && (
                <div className="grid grid-cols-1 gap-2">
                  <Field label="Observation ID" value={obs.observation_id} />
                  <Field label="Canonical Record ID" value={obs.canonical_record_id} />
                  <Field label="Source / Provider" value={obs.field_observation_meta?.operator ?? 'Open-Meteo.com'} mono={false} />
                  <Field label="Observation Type" value={obs.observation_type} />
                  <Field label="Measurement" value={obs.measurements?.length ? `${obs.measurements[0].value} ${obs.measurements[0].unit} (${obs.measurements[0].metric_name})` : 'No measurements'} />
                  <Field label="Timestamp" value={obs.observation_timestamp} />
                  <Field label="Location" value={`${obs.latitude}°N, ${obs.longitude}°E`} />
                  <Field label="Altitude" value={obs.altitude_m != null ? `${obs.altitude_m} m` : 'null'} />
                  <Field label="GNSS Status" value={obs.gnss_status} />
                  <Field label="Calibration" value={obs.calibration_status} />
                  <Field label="Capture Method" value={obs.capture_method} />
                  <Field label="Provenance Ref" value={obs.provenance_reference} />
                  <Field label="Data State" value={obs.data_state} />
                  <Field label="Retrieval Trace ID" value={pipeline.group1Response?.trace_id} />
                </div>
              )}
            </SectionCard>

            <SectionCard icon={<Brain className="w-4 h-4 text-violet-400" />} title="Group 2 — Context & Decision" status={pipeline.group2Status}>
              {pipeline.group2Status === 'idle' && <span className="text-[10px] text-muted-foreground italic">Awaiting Group 1 result…</span>}
              {pipeline.group2Status === 'loading' && <span className="text-[10px] text-muted-foreground">Deriving ruling from canonical observation…</span>}
              {pipeline.group2Status === 'error' && <div className="flex flex-col gap-1"><span className="text-[10px] text-rose-400 font-bold">GROUP 2 ERROR</span><span className="text-[10px] text-rose-300 break-all">{pipeline.group2Error}</span></div>}
              {pipeline.group2Status === 'success' && ruling && (
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col gap-2">
                    <span className="text-[9px] text-muted-foreground uppercase tracking-wider border-b border-border/40 pb-1">Context</span>
                    <div className="flex items-center justify-between">
                      <Field label="Context ID" value={ruling.context_id === null ? 'null' : ruling.context_id} />
                      <StatusPill label="CONTEXT NOT AVAILABLE" tone="amber" />
                    </div>
                    <Field label="Context Status" value="NOT VERIFIED" />
                    <Field label="Missing Critical Data" value={ruling.evidence.missing_critical_data as string ?? 'NONE_BUT_UNVERIFIED'} />
                    <Field label="Scientific Gap" value={ruling.provenance?.message ?? '—'} mono={false} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <span className="text-[9px] text-muted-foreground uppercase tracking-wider border-b border-border/40 pb-1">Decision</span>
                    <div className="flex items-center justify-between">
                      <Field label="Ruling" value={ruling.ruling} />
                      <StatusPill label={ruling.ruling} tone={ruling.ruling === 'ABSTAIN' ? 'amber' : ruling.ruling === 'ALLOW' ? 'green' : 'red'} />
                    </div>
                    <Field label="Decision Reason" value={ruling.provenance?.reason ?? '—'} mono={false} />
                    <Field label="Action Eligibility" value={String(ruling.action_eligibility)} />
                    <Field label="Abstention Required" value={String(ruling.abstention_required)} />
                    <Field label="Action Request" value={ruling.action_request === null ? 'null' : JSON.stringify(ruling.action_request)} />
                    <Field label="Observation ID (preserved)" value={ruling.observation_id} />
                    <Field label="Canonical Record ID (preserved)" value={ruling.canonical_record_id} />
                  </div>
                </div>
              )}
            </SectionCard>

            <SectionCard icon={<ShieldCheck className="w-4 h-4 text-emerald-400" />} title="Group 4 — Governance" status={pipeline.group4Status}>
              {pipeline.group4Status === 'idle' && <span className="text-[10px] text-muted-foreground italic">Awaiting Group 2 ruling…</span>}
              {pipeline.group4Status === 'loading' && <span className="text-[10px] text-muted-foreground">Submitting to Decision Brain (/vana/execute)…</span>}
              {pipeline.group4Status === 'error' && <div className="flex flex-col gap-1"><span className="text-[10px] text-rose-400 font-bold">GROUP 4 API ERROR</span><span className="text-[10px] text-rose-300 break-all">{pipeline.group4Error}</span></div>}
              {pipeline.group4Status === 'success' && evidence && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Field label="Status" value={outcome?.status} />
                    <StatusPill label={outcome?.status?.replace(/_/g, ' ').toUpperCase() ?? '—'} tone={outcome?.status === 'governed_abstention' ? 'amber' : 'green'} />
                  </div>
                  <Field label="Event Type" value={evidence.event_type} />
                  <Field label="Ruling" value={evidence.ruling} />
                  <Field label="Decision Action" value={evidence.decision_action} />
                  <Field label="Governance Allowed" value={String(evidence.governance_allowed)} />
                  <Field label="Context ID" value={evidence.context_id === null ? 'null' : String(evidence.context_id)} />
                  <Field label="Observation ID (preserved)" value={evidence.observation_id} />
                  <Field label="Canonical Record ID (preserved)" value={evidence.canonical_record_id} />
                  <div className="mt-1 flex flex-col gap-2 border-t border-border/40 pt-2">
                    <span className="text-[9px] text-muted-foreground uppercase tracking-wider">Runtime Evidence IDs</span>
                    <Field label="Abstention Record ID" value={evidence.abstention_record_id} />
                    <Field label="Event ID" value={evidence.event_id} />
                    <Field label="Execution ID" value={evidence.execution_id} />
                    <Field label="Recorded At" value={evidence.recorded_at} />
                  </div>
                  <div className="mt-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col gap-1.5">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                      <span className="text-xs text-amber-300 font-bold tracking-wide">CONSTITUTIONAL ABSTENTION ACTIVE</span>
                    </div>
                    <p className="text-[11px] text-amber-200/90 font-sans leading-relaxed">
                      Autonomous action intentionally withheld by governance safety contracts.
                      Required environmental context could not be verified by Group 2, mandating fail-safe non-intervention (Section 4.2).
                    </p>
                    <div className="mt-1 flex items-center gap-2 text-[10px] font-mono text-amber-400">
                      <span>Execution Outcome:</span>
                      <span className="font-bold uppercase">{executionStatus}</span>
                    </div>
                  </div>
                </div>
              )}
            </SectionCard>
          </div>
        </section>
      )}

      {pipeline.group4Status === 'success' && evidence && obs && ruling && (
        <section className="premium-card flex flex-col gap-4">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2 flex items-center gap-1.5">
            <GitBranch className="w-4 h-4 text-primary" />Complete Governance Lineage
          </span>
          <div className="flex flex-col gap-0">
            <LineageStep icon={<Eye className="w-3.5 h-3.5" />} label="SOURCE" value={obs.field_observation_meta?.operator ?? 'Open-Meteo.com External API'} sub={`Capture: ${obs.capture_method} · Device: ${obs.device_id}`} tone="blue" />
            <LineageStep icon={<Hash className="w-3.5 h-3.5" />} label="OBSERVATION ID" value={obs.observation_id} sub={`Type: ${obs.observation_type} · Quality: ${obs.quality_status} · Data state: ${obs.data_state}`} tone="blue" />
            <LineageStep icon={<Database className="w-3.5 h-3.5" />} label="CANONICAL RECORD" value={obs.canonical_record_id} sub={`Retrieval: RETRIEVED · Trace: ${pipeline.group1Response?.trace_id}`} tone="blue" />
            <LineageStep icon={<Info className="w-3.5 h-3.5" />} label="CONTEXT" value={ruling.context_id === null ? 'Context ID: null — Not Available' : ruling.context_id} sub={`Status: Context not verified · Gap: ${ruling.provenance?.reason}`} tone="amber" />
            <LineageStep icon={<Brain className="w-3.5 h-3.5" />} label="GROUP 2 DECISION" value={`Ruling: ${ruling.ruling}`} sub={`Action eligibility: ${ruling.action_eligibility} · Abstention required: ${ruling.abstention_required} · Reason: ${ruling.provenance?.reason}`} tone="amber" />
            <LineageStep icon={<ShieldCheck className="w-3.5 h-3.5" />} label="GROUP 4 GOVERNANCE" value={`Status: ${evidence.event_type} · Decision action: ${evidence.decision_action}`} sub={`Governance allowed: ${evidence.governance_allowed} · Abstention record: ${evidence.abstention_record_id}`} tone="amber" />
            <LineageStep icon={<Activity className="w-3.5 h-3.5" />} label="GOVERNED OUTCOME" value={executionStatus} sub={`event_id: ${evidence.event_id} · execution_id: ${evidence.execution_id}`} tone={executionStatus === 'NOT EXECUTED' ? 'amber' : 'green'} isLast />
          </div>
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { q: '1. Where did this observation originate?', a: `${obs.field_observation_meta?.operator ?? 'Open-Meteo.com'} via ${obs.capture_method}` },
              { q: '2. What was its observation ID?', a: obs.observation_id },
              { q: '3. What canonical record represents it?', a: obs.canonical_record_id },
              { q: '4. Was the canonical record successfully retrieved?', a: `YES — status: ${pipeline.group1Response?.status}` },
              { q: '5. What context was available?', a: ruling.context_id === null ? 'No context — context_id is null' : `Context ID: ${ruling.context_id}` },
              { q: '6. Was context missing?', a: ruling.context_id === null ? 'YES — context not verified' : 'NO' },
              { q: '7. What decision did Group 2 produce?', a: `${ruling.ruling} (action_eligibility: ${ruling.action_eligibility})` },
              { q: '8. Why?', a: ruling.provenance?.message ?? ruling.provenance?.reason ?? '—' },
              { q: '9. Was action eligible?', a: String(ruling.action_eligibility) },
              { q: '10. What did Group 4 decide?', a: `${evidence.event_type} — decision_action: ${evidence.decision_action}` },
              { q: '11. Was an action executed?', a: executionStatus },
              { q: '12. What are the runtime evidence IDs?', a: `abstention: ${evidence.abstention_record_id} · event: ${evidence.event_id} · exec: ${evidence.execution_id}` },
            ].map(({ q, a }, i) => (
              <div key={i} className="flex flex-col gap-0.5 p-3 bg-secondary/15 border border-border/40 rounded-lg">
                <span className="text-[9px] text-muted-foreground">{q}</span>
                <span className="text-[10px] text-foreground font-mono break-all">{a}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!pipeline.selectedObservationId && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 py-20 text-center">
          <Leaf className="w-12 h-12 text-emerald-500/40" />
          <div>
            <h3 className="font-bold text-sm font-sans text-foreground">Select an Observation to Begin</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">Choose a region above to trigger the live Group 1 → Group 2 → Group 4 governance pipeline. All data comes from live runtime APIs.</p>
          </div>
        </div>
      )}
    </div>
  );
}
