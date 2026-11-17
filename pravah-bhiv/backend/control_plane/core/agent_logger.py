#!/usr/bin/env python3
"""
Agent Logger
Structured logging for autonomous agent operations with agent_id, agent_state, and last_decision tracking.
"""

import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class AgentLogger:
    """Structured logger for agent operations."""
    
    def __init__(self, agent_id: str, log_dir: str = "logs/agent", log_level: int = logging.INFO):
        """Initialize agent logger.
        
        Args:
            agent_id: Unique agent identifier
            log_dir: Directory for log files
            log_level: Logging level
        """
        self.agent_id = agent_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create loggers
        self._setup_loggers(log_level)
        
        # Track last decision
        self.last_decision: Optional[Dict[str, Any]] = None
    
    def _setup_loggers(self, log_level: int):
        """Set up logging handlers."""
        # Main runtime log
        self.runtime_logger = logging.getLogger(f"agent.{self.agent_id}.runtime")
        self.runtime_logger.setLevel(log_level)
        
        runtime_handler = logging.FileHandler(
            self.log_dir / "agent_runtime.log",
            encoding='utf-8'
        )
        runtime_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.runtime_logger.addHandler(runtime_handler)
        
        # Proof log (JSONL format for auditability)
        self.proof_log_path = self.log_dir / "agent_proof.jsonl"
        
        # Decision log
        self.decision_logger = logging.getLogger(f"agent.{self.agent_id}.decisions")
        self.decision_logger.setLevel(log_level)
        
        decision_handler = logging.FileHandler(
            self.log_dir / "agent_decisions.log",
            encoding='utf-8'
        )
        decision_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.decision_logger.addHandler(decision_handler)
        
        # Console handler (optional)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - [%(levelname)s] %(message)s')
        )
        self.runtime_logger.addHandler(console_handler)
    
    def _create_base_context(self, agent_state: Optional[str] = None) -> Dict[str, Any]:
        """Create base logging context with agent_id, agent_state, last_decision.
        
        Args:
            agent_state: Current agent state
            
        Returns:
            Dictionary with base context
        """
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
        }
        
        if agent_state:
            context["agent_state"] = agent_state
        
        if self.last_decision:
            context["last_decision"] = self.last_decision
        
        return context
    
    def log_state_transition(self, from_state: str, to_state: str, reason: str = ""):
        """Log agent state transition.
        
        Args:
            from_state: Previous state
            to_state: New state
            reason: Reason for transition
        """
        context = self._create_base_context(to_state)
        context.update({
            "event": "state_transition",
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason
        })
        
        self._write_proof_log(context)
        self.runtime_logger.info(f"State transition: {from_state} -> {to_state} ({reason})")
    
    def log_decision(self, decision_type: str, decision_data: Dict[str, Any], agent_state: str):
        """Log agent decision.
        
        Args:
            decision_type: Type of decision
            decision_data: Decision details
            agent_state: Current agent state
        """
        self.last_decision = {
            "type": decision_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": decision_data
        }
        
        context = self._create_base_context(agent_state)
        context.update({
            "event": "decision",
            "decision_type": decision_type,
            "decision_data": decision_data
        })
        
        self._write_proof_log(context)
        self.decision_logger.info(f"Decision: {decision_type} - {json.dumps(decision_data)}")
    
    def log_action(self, action_type: str, action_data: Dict[str, Any], agent_state: str):
        """Log agent action.
        
        Args:
            action_type: Type of action
            action_data: Action details
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        context.update({
            "event": "action",
            "action_type": action_type,
            "action_data": action_data
        })
        
        self._write_proof_log(context)
        self.runtime_logger.info(f"Action: {action_type} - {json.dumps(action_data)}")
    
    def log_observation(self, observation_type: str, observation_data: Dict[str, Any], agent_state: str):
        """Log agent observation.
        
        Args:
            observation_type: Type of observation
            observation_data: Observation details
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        context.update({
            "event": "observation",
            "observation_type": observation_type,
            "observation_data": observation_data
        })
        
        self._write_proof_log(context)
        self.runtime_logger.debug(f"Observation: {observation_type} - {json.dumps(observation_data)}")
    
    def log_heartbeat(self, agent_state: str, uptime_seconds: float):
        """Log agent heartbeat.
        
        Args:
            agent_state: Current agent state
            uptime_seconds: Agent uptime in seconds
        """
        context = self._create_base_context(agent_state)
        context.update({
            "event": "heartbeat",
            "uptime_seconds": uptime_seconds
        })
        
        self._write_proof_log(context)
        self.runtime_logger.debug(f"Heartbeat: state={agent_state}, uptime={uptime_seconds:.1f}s")
    
    def log_error(self, error_type: str, error_message: str, agent_state: str, error_data: Optional[Dict[str, Any]] = None):
        """Log agent error.
        
        Args:
            error_type: Type of error
            error_message: Error message
            agent_state: Current agent state
            error_data: Additional error details
        """
        context = self._create_base_context(agent_state)
        context.update({
            "event": "error",
            "error_type": error_type,
            "error_message": error_message,
            "error_data": error_data or {}
        })
        
        self._write_proof_log(context)
        self.runtime_logger.error(f"Error: {error_type} - {error_message}")
    
    def log_autonomous_operation(self, operation: str, details: Dict[str, Any], agent_state: str):
        """Log autonomous operation proof.
        
        Args:
            operation: Operation name
            details: Operation details
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        context.update({
            "event": "autonomous_operation",
            "operation": operation,
            "details": details,
            "proof": "no_manual_intervention"
        })
        
        self._write_proof_log(context)
        self.runtime_logger.info(f"Autonomous operation: {operation}")
    
    def _write_proof_log(self, data: Dict[str, Any]):
        """Write to proof log in JSONL format.
        
        Args:
            data: Data to log
        """
        with open(self.proof_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data) + '\n')
    
    def info(self, message: str, agent_state: Optional[str] = None):
        """Log info message.
        
        Args:
            message: Log message
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        self.runtime_logger.info(f"{message} | Context: {json.dumps(context)}")
    
    def debug(self, message: str, agent_state: Optional[str] = None):
        """Log debug message.
        
        Args:
            message: Log message
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        self.runtime_logger.debug(f"{message} | Context: {json.dumps(context)}")
    
    def warning(self, message: str, agent_state: Optional[str] = None):
        """Log warning message.
        
        Args:
            message: Log message
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        self.runtime_logger.warning(f"{message} | Context: {json.dumps(context)}")
    
    def error(self, message: str, agent_state: Optional[str] = None):
        """Log error message.
        
        Args:
            message: Log message
            agent_state: Current agent state
        """
        context = self._create_base_context(agent_state)
        self.runtime_logger.error(f"{message} | Context: {json.dumps(context)}")
