# Event Schema Documentation

EVENT_TYPES = {
    # Deployment Events
    "deploy.started": {"dataset": "str", "timestamp": "str"},
    "deploy.success": {"dataset": "str", "response_time": "float"},
    "deploy.failure": {"dataset": "str", "response_time": "float", "error": "str"},
    
    # Issue Detection Events
    "issue.detected": {"failure_type": "str", "reason": "str", "dataset": "str"},
    "issue.resolved": {"failure_type": "str", "resolution": "str"},
    
    # Healing Events
    "heal.triggered": {"state": "str", "strategy": "str"},
    "heal.success": {"strategy": "str", "response_time": "float"},
    "heal.failure": {"strategy": "str", "error": "str"},
    
    # System Events
    "system.up": {"reason": "str"},
    "system.down": {"reason": "str"},
    
    # RL Events
    "rl.action_chosen": {"state": "str", "action": "str", "q_value": "float"},
    "rl.learned": {"state": "str", "action": "str", "reward": "float", "new_q": "float"},
    
    # User Events
    "user.feedback": {"state": "str", "action": "str", "feedback": "str"}
}