# MCP-Bus Schema Unification

MCP_EVENT_MAPPING = {
    # Bus Event -> MCP Event
    "deploy.success": "deployment_completed",
    "deploy.failure": "deployment_failed", 
    "issue.detected": "anomaly_detected",
    "heal.triggered": "healing_initiated",
    "heal.success": "healing_completed",
    "system.up": "system_online",
    "system.down": "system_offline",
    "rl.learned": "agent_learned"
}

MCP_MESSAGE_SCHEMA = {
    "context_id": "str",      # Unique context identifier
    "timestamp": "str",       # ISO format timestamp
    "event_type": "str",      # MCP event type
    "payload": "dict",        # Event data
    "source": "str",          # Message source (sovereign_bus/mcp_agent)
    "processed": "bool"       # Processing flag
}

# Unified context ID format: ctx_YYYYMMDD_HHMMSS_agent
def generate_context_id(agent_name="bus"):
    from datetime import datetime
    return f"ctx_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{agent_name}"

# Key mappings for Ritesh's mcp_manager.py compatibility
RITESH_KEY_MAPPING = {
    "failure_type": "anomaly_type",
    "response_time": "execution_time_ms", 
    "dataset": "data_source",
    "strategy": "healing_action",
    "q_value": "confidence_score"
}