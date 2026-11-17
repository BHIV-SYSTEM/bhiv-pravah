# FULL EXECUTION TRACE

## 1. INPUT (Monitoring Signal)
{
  "service_id": "service-1",
  "cpu": 95,
  "issue_type": "high_cpu"
}

## 2. INGESTION
Endpoint: /control-plane/runtime-ingest  
Status: accepted  

## 3. DECISION
Action: scale_up  
Reason: CPU above threshold  
Confidence: 0.91  

## 4. GOVERNANCE
Environment: DEV  
Allowed Actions: ["noop", "scale_up", "scale_down", "restart"]  
Result: allowed  

## 5. EXECUTION
Target: Rayyan /execute-action  
Payload:
{
  "action": "scale_up",
  "service_id": "service-1"
}

## 6. EXECUTION RESPONSE
{
  "status": "executed",
  "reason": "DOCKER_SCALE_UP simulated for service-1"
}

## 7. FINAL OUTPUT
{
  "status": "executed",
  "action": "scale_up"
}