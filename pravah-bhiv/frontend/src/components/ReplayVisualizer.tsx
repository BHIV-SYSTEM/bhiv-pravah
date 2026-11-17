'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Shield, Brain, Terminal, FileCheck, HelpCircle, Check, X } from 'lucide-react';

interface VisualizerNode {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<any>;
  status: 'pending' | 'active' | 'success' | 'failed';
  timestamp?: number | string;
  details?: Record<string, any>;
}

export default function ReplayVisualizer({ events }: { events: any[] }) {
  // Extract event stages
  const hasDetection = events.some(e => e.state === 'detection' || e.state?.toLowerCase().includes('detect') || e.event_type === 'detection');
  const hasPayload = events.some(e => e.state === 'payload_emitted' || e.event_type === 'payload_emitted');
  const hasAction = events.some(e => e.state === 'action_received' || e.event_type === 'action_received');
  const hasExecution = events.some(e => e.state === 'execution_result' || e.event_type === 'execution_result');
  const hasVerification = events.some(e => e.state === 'verification' || e.event_type === 'verification');

  // Verify states
  const verifyEvent = events.find(e => e.state === 'verification' || e.event_type === 'verification');
  const isVerified = verifyEvent?.details?.verified === true || verifyEvent?.payload?.verified === true;
  
  const executionEvent = events.find(e => e.state === 'execution_result' || e.event_type === 'execution_result');
  const isExecutionFailed = executionEvent?.details?.status === 'blocked' || executionEvent?.details?.status === 'failed';

  const nodes: VisualizerNode[] = [
    {
      id: 'detect',
      label: 'Detection',
      description: 'Anomaly / Event detected',
      icon: Shield,
      status: hasDetection ? 'success' : 'pending',
      timestamp: events.find(e => e.state === 'detection' || e.event_type === 'detection')?.timestamp,
      details: events.find(e => e.state === 'detection' || e.event_type === 'detection')?.details
    },
    {
      id: 'payload',
      label: 'Payload Ingest',
      description: 'Data packet normalization',
      icon: Terminal,
      status: hasPayload ? 'success' : (hasDetection ? 'active' : 'pending'),
      timestamp: events.find(e => e.state === 'payload_emitted' || e.event_type === 'payload_emitted')?.timestamp
    },
    {
      id: 'decision',
      label: 'RL Decision',
      description: 'Optimized action selection',
      icon: Brain,
      status: hasAction ? 'success' : (hasPayload ? 'active' : 'pending'),
      timestamp: events.find(e => e.state === 'action_received' || e.event_type === 'action_received')?.timestamp,
      details: events.find(e => e.state === 'action_received' || e.event_type === 'action_received')?.details
    },
    {
      id: 'execute',
      label: 'Action Execution',
      description: 'Provisioning or Scaling',
      icon: PlaySquareIcon,
      status: hasExecution ? (isExecutionFailed ? 'failed' : 'success') : (hasAction ? 'active' : 'pending'),
      timestamp: executionEvent?.timestamp,
      details: executionEvent?.details
    },
    {
      id: 'verify',
      label: 'Verification',
      description: 'Attestation & validation',
      icon: FileCheck,
      status: hasVerification ? (isVerified ? 'success' : 'failed') : (hasExecution && !isExecutionFailed ? 'active' : 'pending'),
      timestamp: verifyEvent?.timestamp,
      details: verifyEvent?.details
    }
  ];

  function PlaySquareIcon(props: any) {
    return (
      <svg
        {...props}
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect width="18" height="18" x="3" y="3" rx="2" />
        <path d="m9 17 6-5-6-5v10z" />
      </svg>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'border-emerald-500 bg-emerald-500/10 text-emerald-500';
      case 'failed': return 'border-rose-500 bg-rose-500/10 text-rose-500';
      case 'active': return 'border-primary bg-primary/10 text-primary animate-pulse';
      default: return 'border-border bg-secondary/30 text-muted-foreground';
    }
  };

  const getConnectorColor = (status: string) => {
    switch (status) {
      case 'success': return 'bg-emerald-500';
      case 'failed': return 'bg-rose-500';
      case 'active': return 'bg-primary';
      default: return 'bg-border';
    }
  };

  return (
    <div className="flex flex-col gap-6 p-4 border border-border bg-card rounded-xl shadow-sm overflow-hidden select-none">
      <div className="flex items-center justify-between border-b border-border/60 pb-3">
        <h4 className="font-semibold text-xs text-foreground uppercase tracking-wider font-mono">Execution Lineage Flow</h4>
        <span className="text-[10px] text-muted-foreground bg-secondary px-2 py-0.5 rounded border border-border/60 font-mono">
          {events.length} events replayed
        </span>
      </div>

      {/* Graph Line layout */}
      <div className="relative flex md:flex-row flex-col justify-between items-center py-6 gap-8 md:gap-4">
        {nodes.map((node, index) => {
          const NodeIcon = node.icon;
          const isLast = index === nodes.length - 1;

          return (
            <React.Fragment key={node.id}>
              {/* Node Card */}
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex flex-col items-center text-center relative z-10 w-full md:w-32 group"
              >
                {/* Node circle */}
                <div className={`w-12 h-12 rounded-full border-2 flex items-center justify-center transition-all duration-300 ${getStatusColor(node.status)}`}>
                  {node.status === 'success' && node.id === 'verify' ? (
                    <Check className="w-5 h-5 stroke-[3px]" />
                  ) : node.status === 'failed' ? (
                    <X className="w-5 h-5 stroke-[3px]" />
                  ) : (
                    <NodeIcon className="w-5 h-5" />
                  )}
                </div>
                
                <span className="text-xs font-semibold text-foreground mt-3 font-sans group-hover:text-primary transition-colors">
                  {node.label}
                </span>
                
                <span className="text-[10px] text-muted-foreground mt-1 max-w-[120px] md:inline hidden leading-relaxed">
                  {node.description}
                </span>

                {node.timestamp && (
                  <span className="text-[9px] font-mono text-muted-foreground mt-1.5 bg-secondary px-1.5 py-0.5 rounded border border-border/40">
                    {(() => {
                      const num = Number(node.timestamp);
                      if (!isNaN(num)) {
                        return new Date(num * 1000).toLocaleTimeString();
                      }
                      return new Date(node.timestamp).toLocaleTimeString();
                    })()}
                  </span>
                )}
              </motion.div>

              {/* Connector line */}
              {!isLast && (
                <div className="flex-1 h-0.5 md:w-full w-0.5 min-h-[30px] md:min-h-[auto] relative bg-border select-none pointer-events-none md:my-0 -my-4">
                  <div className={`absolute top-0 left-0 w-full h-full origin-left transition-all duration-500 ${getConnectorColor(node.status)}`} style={{ transform: node.status === 'success' ? 'scaleX(1)' : 'scaleX(0)' }} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Details Box of last active/failed state */}
      {events.length > 0 && (
        <div className="mt-2 bg-secondary/35 border border-border/60 rounded-lg p-3 font-mono text-[10px] text-muted-foreground flex flex-col gap-1.5">
          <span className="text-foreground/80 font-bold uppercase tracking-wider text-[9px] border-b border-border/40 pb-1">Lineage Metadata Details</span>
          {isExecutionFailed && (
            <div className="text-rose-500 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
              <span>Execution Blocked: {executionEvent?.details?.error || 'Rejected by action governance boundary'}</span>
            </div>
          )}
          {isVerified && (
            <div className="text-emerald-500 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              <span>Attestation Check: Cryptographically Valid (Lineage Chain Verified)</span>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 mt-1.5 text-foreground/70">
            <div>Trace ID: <span className="text-muted-foreground break-all">{events[0]?.trace_id || '--'}</span></div>
            <div>Execution ID: <span className="text-muted-foreground break-all">{events[0]?.execution_id || '--'}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}
