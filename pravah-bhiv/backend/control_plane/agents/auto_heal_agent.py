import random
import os
import csv
import datetime
import shutil
from utils import trigger_dashboard_deployment
from control_plane.core.base_agent import BaseAgent
from control_plane.core.redis_event_bus import get_redis_bus
from control_plane.core.prod_safety import validate_prod_action, ProductionSafetyError
from control_plane.core.stage_determinism import StageDeterminismLock, log_determinism_status

class AutoHealAgent(BaseAgent):
    """A simple agent that can execute healing strategies."""
    def __init__(self, healing_log_file, env='dev'):
        self.strategies = ['retry_deployment', 'restore_previous_version', 'adjust_thresholds']
        self.env = env
        # Demo-safe Redis behavior - no silent mock mode
        from control_plane.core.redis_demo_behavior import get_redis_bus_demo_safe, RedisUnavailableError
        
        try:
            # Try Redis with explicit stub fallback for demo
            self.redis_bus = get_redis_bus_demo_safe(env, use_stub=True)
        except RedisUnavailableError as e:
            print(f"🚨 CRITICAL: {e}")
            raise  # Fail deterministically
        super().__init__(healing_log_file, "AutoHealAgent")
        self.logger.info("Agent ready", strategies=len(self.strategies))
    
    def get_log_headers(self) -> list:
        return ["timestamp", "strategy", "status", "response_time_ms"]
    
    def run(self):
        pass  # Called by external systems

    def _log_healing_attempt(self, strategy, status, response_time):
        """Log healing attempt using base class method."""
        self._log_entry({
            "strategy": strategy,
            "status": status,
            "response_time_ms": round(response_time, 2)
        })

    def attempt_healing(self, state, dataset_path):
        """Chooses a healing strategy and executes it."""
        # Stage environment: Use deterministic strategy selection for demo predictability
        if StageDeterminismLock.is_stage_env(self.env):
            # Deterministic strategy selection using seed
            seed_input = f"{state}_{dataset_path}"
            strategy = StageDeterminismLock.deterministic_choice(self.strategies, seed_input)
            log_determinism_status(self.env, "AutoHealAgent strategy selection")
            print(f"\n--- Auto-Heal Agent: Deterministic recovery (stage) for state '{state}' using '{strategy}' ---")
        else:
            # Dev/prod: Use random selection
            strategy = random.choice(self.strategies)
            print(f"\n--- Auto-Heal Agent: Initiating random recovery for state '{state}' ---")
        
        return self.execute_action(strategy, dataset_path)

    def execute_action(self, strategy, dataset_path):
        """
        Executes a specific, chosen healing strategy.
        This allows the RL Trainer to command this agent.
        """
        # Production safety check
        try:
            validate_prod_action(strategy, self.env)
        except ProductionSafetyError as e:
            # Do NOT execute - emit refusal event, log refusal, return deterministic response
            refusal_event = {
                "event": "action_refused",
                "env": self.env,
                "status": "refused",
                "latency": 0,
                "timestamp": datetime.datetime.now().isoformat(),
                "action_type": strategy,
                "reason": "prod_safety_block",
                "error_message": str(e)
            }
            
            # Emit refusal event to Redis
            self.redis_bus.publish("action.refused", refusal_event)
            
            # Log refusal
            self._log_healing_attempt(strategy, "refused", 0)
            self.logger.info("Action refused", strategy=strategy, env=self.env, reason="prod_safety_block")
            
            # Return deterministic response
            return "refused", 0, "prod_safety_block", strategy
        
        self.logger.info(f"Executing healing strategy", strategy=strategy, dataset=dataset_path)
        status, response_time = "failure", 0
        heal_type = "unknown_strategy"

        if strategy == 'retry_deployment':
            status, response_time = self._retry_deployment()
            heal_type = "heal_retry"
        elif strategy == 'restore_previous_version':
            status, response_time = self._restore_previous_version(dataset_path)
            heal_type = "heal_restore"
        elif strategy == 'adjust_thresholds':
            status, response_time = self._adjust_thresholds()
            heal_type = "heal_adjust"
        
        # Guaranteed event emission - no silent failures
        from control_plane.core.guaranteed_events import emit_deploy_event
        try:
            emit_deploy_event(self.env, status, response_time, dataset_path, strategy=strategy)
        except Exception as e:
            print(f"CRITICAL: Event emission failed for {strategy}: {e}")
            # Re-raise to ensure no silent failures
            raise
        
        self._log_healing_attempt(strategy, status, response_time)
        self.logger.log_action("healing_completed", status, 
                              strategy=strategy, 
                              response_time=response_time,
                              heal_type=heal_type)
        
        # Publish healing result to Redis bus
        self.redis_bus.publish("heal.completed", {
            "strategy": strategy,
            "status": status,
            "response_time": response_time,
            "heal_type": heal_type,
            "environment": self.env
        })
        
        return status, response_time, heal_type, strategy

    def _retry_deployment(self):
        """Healing Action 1: Simply try deploying again."""
        return trigger_dashboard_deployment(should_fail=False, env=self.env)

    def _restore_previous_version(self, dataset_path):
        """Healing Action 2: Roll back by restoring the data from backup."""
        backup_path = dataset_path + ".bak"
        if os.path.exists(backup_path):
            try:
                shutil.copyfile(backup_path, dataset_path)
                print(f"  -> Successfully restored '{dataset_path}' from backup.")
                return trigger_dashboard_deployment(should_fail=False, env=self.env)
            except Exception as e:
                print(f"  -> Error while restoring backup: {e}")
                return "failure", 0
        else:
            print("  -> No backup file found. Cannot restore.")
            return "failure", 0

    def _adjust_thresholds(self):
        """Healing Action 3: Simulate adjusting a performance threshold."""
        # Stage environment: Fixed response time for demo predictability
        if StageDeterminismLock.is_stage_env(self.env):
            response_time = StageDeterminismLock.get_deterministic_response_time('heal')
            return "success", response_time  # Deterministic timing for predictable demo
        else:
            return "success", 200  # Original behavior for dev/prod

