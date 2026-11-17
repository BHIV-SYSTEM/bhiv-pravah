"""
Self-Restraint Module
Implements intentional self-blocking rules for the autonomous agent.

The agent can block itself based on:
1. Conflicting signals (e.g., high CPU and low CPU simultaneously)
2. Low confidence (decision uncertainty below threshold)
3. Memory instability risk (too many recent failures)
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum


class BlockReason(Enum):
    """Reasons for self-imposed blocking."""
    CONFLICTING_SIGNALS = "conflicting_signals"
    LOW_CONFIDENCE = "low_confidence"
    MEMORY_INSTABILITY_RISK = "memory_instability_risk"
    INSUFFICIENT_DATA = "insufficient_data"
    SAFETY_THRESHOLD_EXCEEDED = "safety_threshold_exceeded"
    UNCERTAINTY_TOO_HIGH = "uncertainty_too_high"
    SIGNAL_CONFLICT_REQUIRES_OBSERVATION = "signal_conflict_requires_observation"


@dataclass
class BlockDecision:
    """Represents a self-imposed block decision."""
    should_block: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    self_imposed: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'should_block': self.should_block,
            'block_reason': self.reason,
            'block_details': self.details,
            'self_imposed': self.self_imposed
        }


class SelfRestraint:
    """Self-restraint module for autonomous agent.
    
    Evaluates conditions that should trigger intentional self-blocking.
    """
    
    def __init__(
        self,
        min_confidence: float = 0.6,
        max_instability_score: int = 75,
        max_recent_failures: int = 5
    ):
        """Initialize self-restraint module.
        
        Args:
            min_confidence: Minimum decision confidence threshold
            max_instability_score: Maximum allowed instability score (0-100)
            max_recent_failures: Maximum recent failures before blocking
        """
        self.min_confidence = min_confidence
        self.max_instability_score = max_instability_score
        self.max_recent_failures = max_recent_failures
    
    def evaluate_block(
        self,
        decision_data: Optional[Dict[str, Any]] = None,
        memory_signals: Optional[Dict[str, Any]] = None,
        health_signals: Optional[Dict[str, Any]] = None
    ) -> BlockDecision:
        """Evaluate whether agent should self-block.
        
        Checks multiple conditions in priority order:
        1. Conflicting signals
        2. Memory instability risk
        3. Low confidence
        4. Insufficient data
        
        Args:
            decision_data: Decision information (confidence, action, etc.)
            memory_signals: Memory context signals
            health_signals: Health monitoring signals
            
        Returns:
            BlockDecision indicating whether to block and why
        """
        # Rule 1: Detect conflicting health signals
        if health_signals:
            block = self._check_conflicting_signals(health_signals)
            if block.should_block:
                return block
        
        # Rule 2: Check memory instability risk
        if memory_signals:
            block = self._check_memory_risk(memory_signals)
            if block.should_block:
                return block
        
        # Rule 3: Check decision confidence
        if decision_data:
            block = self._check_confidence(decision_data)
            if block.should_block:
                return block
        
        # Rule 4: Check for insufficient data
        block = self._check_insufficient_data(decision_data, memory_signals, health_signals)
        if block.should_block:
            return block
        
        # No blocking conditions met
        return BlockDecision(should_block=False)
    
    def _check_conflicting_signals(self, health_signals: Dict[str, Any]) -> BlockDecision:
        """Check for conflicting health signals.
        
        Examples of conflicts:
        - cpu_high=True and cpu_low=True
        - memory_high=True and memory_low=True
        
        Args:
            health_signals: Health monitoring data
            
        Returns:
            BlockDecision
        """
        conflicts = []
        
        # Check CPU conflicts
        if health_signals.get('cpu_high') and health_signals.get('cpu_low'):
            conflicts.append('cpu: both high and low')
        
        # Check memory conflicts
        if health_signals.get('memory_high') and health_signals.get('memory_low'):
            conflicts.append('memory: both high and low')
        
        # Check error rate conflicts
        if health_signals.get('error_rate_high') and health_signals.get('error_rate_zero'):
            conflicts.append('error_rate: both high and zero')
        
        if conflicts:
            return BlockDecision(
                should_block=True,
                reason=BlockReason.CONFLICTING_SIGNALS.value,
                details={'conflicts': conflicts}
            )
        
        return BlockDecision(should_block=False)
    
    def _check_memory_risk(self, memory_signals: Dict[str, Any]) -> BlockDecision:
        """Check if memory indicates high risk.
        
        Blocks if:
        - Instability score > threshold
        - Too many recent failures
        
        Args:
            memory_signals: Memory context data
            
        Returns:
            BlockDecision
        """
        instability_score = memory_signals.get('instability_score', 0)
        recent_failures = memory_signals.get('recent_failures', 0)
        
        # Check instability score
        if instability_score > self.max_instability_score:
            return BlockDecision(
                should_block=True,
                reason=BlockReason.MEMORY_INSTABILITY_RISK.value,
                details={
                    'instability_score': instability_score,
                    'threshold': self.max_instability_score,
                    'recent_failures': recent_failures
                }
            )
        
        # Check failure count
        if recent_failures > self.max_recent_failures:
            return BlockDecision(
                should_block=True,
                reason=BlockReason.MEMORY_INSTABILITY_RISK.value,
                details={
                    'recent_failures': recent_failures,
                    'threshold': self.max_recent_failures,
                    'instability_score': instability_score
                }
            )
        
        return BlockDecision(should_block=False)
    
    def _check_confidence(self, decision_data: Dict[str, Any]) -> BlockDecision:
        """Check if decision confidence is below threshold.
        
        Args:
            decision_data: Decision information
            
        Returns:
            BlockDecision
        """
        confidence = decision_data.get('confidence', 1.0)
        
        if confidence < self.min_confidence:
            return BlockDecision(
                should_block=True,
                reason=BlockReason.LOW_CONFIDENCE.value,
                details={
                    'confidence': confidence,
                    'threshold': self.min_confidence
                }
            )
        
        return BlockDecision(should_block=False)
    
    def _check_insufficient_data(
        self,
        decision_data: Optional[Dict[str, Any]],
        memory_signals: Optional[Dict[str, Any]],
        health_signals: Optional[Dict[str, Any]]
    ) -> BlockDecision:
        """Check if there's insufficient data to make a decision.
        
        Args:
            decision_data: Decision information
            memory_signals: Memory context
            health_signals: Health data
            
        Returns:
            BlockDecision
        """
        # If we have no data at all, block
        if not decision_data and not memory_signals and not health_signals:
            return BlockDecision(
                should_block=True,
                reason=BlockReason.INSUFFICIENT_DATA.value,
                details={'message': 'No decision, memory, or health data available'}
            )
        
        return BlockDecision(should_block=False)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            'min_confidence': self.min_confidence,
            'max_instability_score': self.max_instability_score,
            'max_recent_failures': self.max_recent_failures
        }
    
    def update_config(
        self,
        min_confidence: Optional[float] = None,
        max_instability_score: Optional[int] = None,
        max_recent_failures: Optional[int] = None
    ):
        """Update configuration thresholds.
        
        Args:
            min_confidence: New minimum confidence threshold
            max_instability_score: New max instability score
            max_recent_failures: New max recent failures
        """
        if min_confidence is not None:
            self.min_confidence = min_confidence
        if max_instability_score is not None:
            self.max_instability_score = max_instability_score
        if max_recent_failures is not None:
            self.max_recent_failures = max_recent_failures
    
    def check_uncertainty(self, decision_data: Dict[str, Any], uncertainty_threshold: float = 0.5) -> BlockDecision:
        """Check if decision uncertainty is too high.
        
        When uncertainty is high, agent should NOOP instead of acting.
        Uncertainty = 1 - confidence
        
        Args:
            decision_data: Decision information with confidence score
            uncertainty_threshold: Maximum allowed uncertainty
            
        Returns:
            BlockDecision indicating NOOP if uncertainty too high
        """
        confidence = decision_data.get('confidence', 1.0)
        uncertainty = 1.0 - confidence
        
        if uncertainty > uncertainty_threshold:
            return BlockDecision(
                should_block=True,
                reason=BlockReason.UNCERTAINTY_TOO_HIGH.value,
                details={
                    'confidence': confidence,
                    'uncertainty': uncertainty,
                    'threshold': uncertainty_threshold,
                    'recommended_action': 'noop',
                    'message': f'Uncertainty {uncertainty:.2f} exceeds threshold {uncertainty_threshold:.2f} → NOOP'
                }
            )
        
        return BlockDecision(should_block=False)
    
    def should_observe_instead_of_act(
        self,
        health_signals: Optional[Dict[str, Any]] = None,
        memory_signals: Optional[Dict[str, Any]] = None
    ) -> BlockDecision:
        """Determine if agent should observe instead of act.
        
        When signals conflict, agent should observe to gather more data
        rather than acting on unreliable information.
        
        Args:
            health_signals: Health monitoring signals
            memory_signals: Memory context signals
            
        Returns:
            BlockDecision indicating observation mode if conditions met
        """
        # Check for signal conflicts
        if health_signals:
            conflict_check = self._check_conflicting_signals(health_signals)
            if conflict_check.should_block:
                # Convert to observation mode recommendation
                return BlockDecision(
                    should_block=True,
                    reason=BlockReason.SIGNAL_CONFLICT_REQUIRES_OBSERVATION.value,
                    details={
                        'conflicts': conflict_check.details.get('conflicts', []),
                        'recommended_action': 'observe',
                        'message': 'Conflicting signals detected → observe instead of act'
                    }
                )
        
        # Check for unstable memory patterns
        if memory_signals:
            instability = memory_signals.get('instability_score', 0)
            if instability > 50:  # Moderate instability threshold
                return BlockDecision(
                    should_block=True,
                    reason=BlockReason.SIGNAL_CONFLICT_REQUIRES_OBSERVATION.value,
                    details={
                        'instability_score': instability,
                        'recommended_action': 'observe',
                        'message': f'Moderate instability ({instability}) → observe for stability'
                    }
                )
        
        return BlockDecision(should_block=False)
