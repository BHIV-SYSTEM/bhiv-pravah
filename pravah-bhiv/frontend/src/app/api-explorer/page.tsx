'use client';

import React, { useState } from 'react';
import { api, decisionBrainApi, controlPlaneApi, observerApi } from '../../services/api';
import { 
  Code, 
  Play, 
  Globe, 
  Send,
  Database,
  Loader2
} from 'lucide-react';
import { toast } from 'sonner';

interface ApiEndpoint {
  port: 8000 | 7000 | 8600;
  method: 'GET' | 'POST';
  path: string;
  description: string;
  payloadTemplate?: string;
}

export default function ApiExplorer() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [jsonPayload, setJsonPayload] = useState('');
  const [responseJson, setResponseJson] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);

  const endpoints: ApiEndpoint[] = [
    // Port 8000
    { port: 8000, method: 'GET', path: '/health', description: 'Brain Health Attestation' },
    { port: 8000, method: 'GET', path: '/live-dashboard', description: 'Real-time Production Analytics Data' },
    { port: 8000, method: 'GET', path: '/recent-activity', description: 'Latest RL Brain Decisions (Last 10)' },
    { port: 8000, method: 'GET', path: '/action-scope', description: 'Environment Scope Rules Matrix' },
    { port: 8000, method: 'POST', path: '/ingest-link', description: 'Add new link to live monitors', payloadTemplate: '{\n  "link": "https://github.com/facebook/react"\n}' },
    
    // Port 7000
    { port: 7000, method: 'GET', path: '/api/control-plane/apps', description: 'List managed apps in registry' },
    { port: 7000, method: 'GET', path: '/api/control-plane/health', description: 'Health Overview metadata' },
    
    // Port 8600
    { port: 8600, method: 'GET', path: '/api/status', description: 'Observer Services audit' },
    { port: 8600, method: 'GET', path: '/api/events', description: 'Historical Telemetry Event logs' },
    { port: 8600, method: 'GET', path: '/api/lineage', description: 'Ecosystem Evidence Bundles' },
  ];

  const handleEndpointSelect = (idx: number) => {
    setSelectedIdx(idx);
    setResponseJson(null);
    const template = endpoints[idx].payloadTemplate;
    setJsonPayload(template || '');
  };

  const handleExecute = async () => {
    const ep = endpoints[selectedIdx];
    setExecuting(true);
    setResponseJson(null);

    try {
      let client = decisionBrainApi;
      if (ep.port === 7000) client = controlPlaneApi;
      if (ep.port === 8600) client = observerApi;

      let res;
      if (ep.method === 'GET') {
        res = await client.get(ep.path);
      } else {
        const body = jsonPayload.trim() ? JSON.parse(jsonPayload.trim()) : {};
        res = await client.post(ep.path, body);
      }

      setResponseJson(JSON.stringify(res.data, null, 2));
      toast.success('Request completed successfully.');
    } catch (err: any) {
      console.error(err);
      const errorMsg = err.response?.data 
        ? JSON.stringify(err.response.data, null, 2) 
        : err.message || 'Unknown network error';
      setResponseJson(errorMsg);
      toast.error('API request failed.');
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6 font-mono text-xs">
      
      {/* Header */}
      <header className="flex justify-between items-end pb-4 border-b border-border/60">
        <div>
          <h2 className="text-xl font-bold font-sans tracking-tight text-foreground flex items-center gap-2">
            <Code className="w-5 h-5 text-primary" />
            API Explorer
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Interactively query backend endpoints on Ports 8000, 7000, and 8600 directly from console
          </p>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        
        {/* Left: Endpoint selectors */}
        <div className="lg:col-span-1 premium-card flex flex-col gap-3">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-2">API Endpoints Catalog</span>
          
          <div className="flex flex-col gap-1.5 overflow-y-auto max-h-[440px] pr-1">
            {endpoints.map((ep, idx) => {
              const isSelected = selectedIdx === idx;
              return (
                <div 
                  key={idx}
                  onClick={() => handleEndpointSelect(idx)}
                  className={`p-2.5 rounded-lg border cursor-pointer flex flex-col gap-1 transition-all duration-150 ${isSelected ? 'bg-primary/10 border-primary' : 'bg-secondary/20 border-border hover:bg-secondary/40'}`}
                >
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="font-extrabold text-foreground">{ep.path}</span>
                    <span className={`px-1.5 py-0.5 rounded font-bold text-[8px] ${ep.method === 'GET' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-blue-500/10 text-blue-500 border border-blue-500/20'}`}>
                      {ep.method}
                    </span>
                  </div>
                  <span className="text-[9px] text-muted-foreground leading-normal">{ep.description}</span>
                  <span className="text-[8px] text-muted-foreground/60 mt-1 uppercase">PORT: {ep.port}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Request & Response console */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          
          {/* Top: Payload editor */}
          {endpoints[selectedIdx]?.method === 'POST' && (
            <div className="premium-card flex flex-col gap-3">
              <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-1.5">Request JSON Payload</span>
              <textarea
                className="bg-secondary/60 border border-border rounded-lg p-3.5 text-xs text-foreground font-mono focus:border-primary outline-none h-28 resize-none shadow-inner"
                value={jsonPayload}
                onChange={(e) => setJsonPayload(e.target.value)}
              />
            </div>
          )}

          {/* Bottom: Executer and Response logs */}
          <div className="premium-card flex-1 flex flex-col gap-4 overflow-hidden h-[330px]">
            <div className="flex justify-between items-center border-b border-border/40 pb-2">
              <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">JSON RESPONSE PAYLOAD</span>
              
              <button
                onClick={handleExecute}
                disabled={executing}
                className="px-5 py-2.5 rounded-lg bg-primary text-primary-foreground hover:opacity-90 font-sans font-extrabold uppercase tracking-wider flex items-center gap-2 text-xs transition-all active:scale-[0.98] shadow-sm shrink-0 border border-primary/20 cursor-pointer"
              >
                {executing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                EXECUTE REQUEST
              </button>
            </div>

            <div className="flex-1 overflow-auto bg-black/40 border border-border/60 rounded-lg p-3.5 text-foreground">
              {responseJson ? (
                <pre className="text-xs font-mono whitespace-pre-wrap selection:bg-primary/30">{responseJson}</pre>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center font-sans text-muted-foreground">
                  <Globe className="w-8 h-8 opacity-20" />
                  <span className="text-xs mt-1.5">No response logs available. Commit a request trigger.</span>
                </div>
              )}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
