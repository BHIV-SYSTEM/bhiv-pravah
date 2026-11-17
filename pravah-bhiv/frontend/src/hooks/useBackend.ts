import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

export function useLiveDashboard(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['liveDashboard'],
    queryFn: api.getLiveDashboard,
    refetchInterval,
    refetchOnWindowFocus: true,
  });
}

export function useAutonomousStatus(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['autonomousStatus'],
    queryFn: api.getAutonomousStatus,
    refetchInterval,
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ['recentActivity'],
    queryFn: api.getRecentActivity,
  });
}

export function useDecisionSummary() {
  return useQuery({
    queryKey: ['decisionSummary'],
    queryFn: api.getDecisionSummary,
  });
}

export function useActionScope() {
  return useQuery({
    queryKey: ['actionScope'],
    queryFn: api.getActionScope,
  });
}

export function useOrchestrationMetrics(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['orchestrationMetrics'],
    queryFn: api.getOrchestrationMetrics,
    refetchInterval,
  });
}

export function useAppRegistry() {
  return useQuery({
    queryKey: ['appRegistry'],
    queryFn: api.getAppRegistry,
  });
}

export function useHealthOverview(refetchInterval = 10000) {
  return useQuery({
    queryKey: ['healthOverview'],
    queryFn: api.getHealthOverview,
    refetchInterval,
  });
}

export function useDecisionHistory(appName: string, limit = 50) {
  return useQuery({
    queryKey: ['decisionHistory', appName, limit],
    queryFn: () => api.getDecisionHistory(appName, limit),
    enabled: !!appName,
  });
}

export function useUnifiedRegistryTrace(traceId: string | null) {
  return useQuery({
    queryKey: ['unifiedRegistryTrace', traceId],
    queryFn: () => api.getUnifiedRegistryTrace(traceId!),
    enabled: !!traceId,
  });
}

export function useObserverStatus(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['observerStatus'],
    queryFn: api.getObserverStatus,
    refetchInterval,
  });
}

export function useObserverEvents(limit = 100, refetchInterval = 5000) {
  return useQuery({
    queryKey: ['observerEvents', limit],
    queryFn: () => api.getObserverEvents(limit),
    refetchInterval,
  });
}

export function useObserverLineage(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['observerLineage'],
    queryFn: api.getObserverLineage,
    refetchInterval,
  });
}

export function useLineageReplay(executionId: string | null) {
  return useQuery({
    queryKey: ['lineageReplay', executionId],
    queryFn: () => api.getLineageReplay(executionId!),
    enabled: !!executionId,
  });
}

export function useVerifyLineage(executionId: string | null) {
  return useQuery({
    queryKey: ['verifyLineage', executionId],
    queryFn: () => api.verifyLineage(executionId!),
    enabled: !!executionId,
  });
}

// Mutations
export function useIngestLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (link: string) => api.ingestLink(link),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['liveDashboard'] });
    },
  });
}

export function useRemoveLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (link: string) => api.removeLink(link),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['liveDashboard'] });
    },
  });
}

export function usePostOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      app_name: string;
      action: 'freeze' | 'clear_freeze' | 'set_freeze';
      duration?: number;
      duration_minutes?: number;
      reason?: string;
    }) => api.postOverride(payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['healthOverview'] });
      queryClient.invalidateQueries({ queryKey: ['decisionHistory', variables.app_name] });
      queryClient.invalidateQueries({ queryKey: ['liveDashboard'] });
    },
  });
}


export function useUnifiedProductHealth(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['unifiedProductHealth'],
    queryFn: api.getUnifiedProductHealth,
    refetchInterval,
  });
}

export function useTrafficMetrics(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['trafficMetrics'],
    queryFn: api.getTrafficMetrics,
    refetchInterval,
  });
}

export function usePerformanceMetrics(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['performanceMetrics'],
    queryFn: api.getPerformanceMetrics,
    refetchInterval,
  });
}

export function useDependencyTopology() {
  return useQuery({
    queryKey: ['dependencyTopology'],
    queryFn: api.getDependencyTopology,
  });
}

export function useIncidents(refetchInterval = 5000) {
  return useQuery({
    queryKey: ['incidents'],
    queryFn: api.getIncidents,
    refetchInterval,
  });
}
