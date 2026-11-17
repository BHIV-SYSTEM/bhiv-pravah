"""
Phase 4 Semantic Guard Engine Tests

Tests the comprehensive semantic validation including:
- Valid execution paths
- Invalid semantic transitions
- Hidden state detection
- Governance state coupling
- Replay chain validation
"""

import pytest
from control_plane.security.semantic_guard_engine import (
    SemanticGuardEngine,
    SemanticFSM,
    SemanticTransitionViolation,
    SemanticViolationReport,
    validate_state_transition,
    validate_state_history,
    validate_replay_chain,
    get_semantic_guard,
)


class TestSemanticFSM:
    """Test the Semantic FSM structure."""
    
    def test_fsm_allowed_transitions(self):
        """Verify FSM transition table."""
        fsm = SemanticFSM()
        
        # Valid transitions
        assert fsm.is_allowed_transition("CREATED", "APPROVED")
        assert fsm.is_allowed_transition("CREATED", "FAILED")
        assert fsm.is_allowed_transition("APPROVED", "EXECUTING")
        assert fsm.is_allowed_transition("EXECUTING", "COMPLETED")
        assert fsm.is_allowed_transition("EXECUTING", "FAILED")
        
        # Invalid transitions
        assert not fsm.is_allowed_transition("CREATED", "EXECUTING")
        assert not fsm.is_allowed_transition("CREATED", "COMPLETED")
        assert not fsm.is_allowed_transition("APPROVED", "COMPLETED")
        assert not fsm.is_allowed_transition("EXECUTING", "APPROVED")
        assert not fsm.is_allowed_transition("COMPLETED", "FAILED")
    
    def test_fsm_prerequisites(self):
        """Verify FSM prerequisites."""
        fsm = SemanticFSM()
        
        assert fsm.get_prerequisites("CREATED") == set()
        assert fsm.get_prerequisites("APPROVED") == {"CREATED"}
        assert fsm.get_prerequisites("EXECUTING") == {"CREATED", "APPROVED"}
        assert fsm.get_prerequisites("COMPLETED") == {"CREATED", "APPROVED", "EXECUTING"}
        assert fsm.get_prerequisites("FAILED") == {"CREATED"}
    
    def test_terminal_states(self):
        """Verify terminal states."""
        fsm = SemanticFSM()
        
        assert fsm.is_terminal("COMPLETED")
        assert fsm.is_terminal("FAILED")
        assert not fsm.is_terminal("CREATED")
        assert not fsm.is_terminal("APPROVED")
        assert not fsm.is_terminal("EXECUTING")


class TestValidSemanticPaths:
    """Test that valid execution paths pass validation."""
    
    def test_full_valid_path(self):
        """Full valid path: CREATED → APPROVED → EXECUTING → COMPLETED"""
        engine = SemanticGuardEngine()
        
        history = ("CREATED",)
        # CREATED → APPROVED
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="CREATED",
            next_state="APPROVED",
            history=history,
        )
        assert result is None, "CREATED → APPROVED should be valid"
        
        history = ("CREATED", "APPROVED")
        # APPROVED → EXECUTING
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="APPROVED",
            next_state="EXECUTING",
            history=history,
        )
        assert result is None, "APPROVED → EXECUTING should be valid"
        
        history = ("CREATED", "APPROVED", "EXECUTING")
        # EXECUTING → COMPLETED
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="EXECUTING",
            next_state="COMPLETED",
            history=history,
        )
        assert result is None, "EXECUTING → COMPLETED should be valid"
    
    def test_failure_from_created(self):
        """CREATED → FAILED is valid."""
        engine = SemanticGuardEngine()
        history = ("CREATED",)
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="CREATED",
            next_state="FAILED",
            history=history,
        )
        assert result is None, "CREATED → FAILED should be valid"
    
    def test_failure_from_approved(self):
        """APPROVED → FAILED is valid."""
        engine = SemanticGuardEngine()
        history = ("CREATED", "APPROVED")
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="APPROVED",
            next_state="FAILED",
            history=history,
        )
        assert result is None, "APPROVED → FAILED should be valid"
    
    def test_failure_from_executing(self):
        """EXECUTING → FAILED is valid."""
        engine = SemanticGuardEngine()
        history = ("CREATED", "APPROVED", "EXECUTING")
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="EXECUTING",
            next_state="FAILED",
            history=history,
        )
        assert result is None, "EXECUTING → FAILED should be valid"


class TestInvalidSemanticJumps:
    """Test that invalid semantic jumps are rejected."""
    
    def test_created_to_completed_invalid(self):
        """CREATED → COMPLETED is INVALID (missing APPROVED, EXECUTING)."""
        engine = SemanticGuardEngine()
        history = ("CREATED",)
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="CREATED",
            next_state="COMPLETED",
            history=history,
        )
        
        assert result is not None, "CREATED → COMPLETED should be invalid"
        assert result.violation_type == SemanticTransitionViolation.STATE_PREREQUISITE_MISSING
        assert "APPROVED" in result.missing_states
        assert "EXECUTING" in result.missing_states
    
    def test_created_to_executing_invalid(self):
        """CREATED → EXECUTING is INVALID (missing APPROVED)."""
        engine = SemanticGuardEngine()
        history = ("CREATED",)
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="CREATED",
            next_state="EXECUTING",
            history=history,
        )
        
        assert result is not None, "CREATED → EXECUTING should be invalid"
        assert result.violation_type == SemanticTransitionViolation.STATE_PREREQUISITE_MISSING
        assert "APPROVED" in result.missing_states
    
    def test_approved_to_completed_invalid(self):
        """APPROVED → COMPLETED is INVALID (missing EXECUTING)."""
        engine = SemanticGuardEngine()
        history = ("CREATED", "APPROVED")
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="APPROVED",
            next_state="COMPLETED",
            history=history,
        )
        
        assert result is not None, "APPROVED → COMPLETED should be invalid"
        assert result.violation_type == SemanticTransitionViolation.STATE_PREREQUISITE_MISSING
        assert "EXECUTING" in result.missing_states


class TestTerminalStateViolations:
    """Test terminal state transition violations."""
    
    def test_failed_to_executing_invalid(self):
        """FAILED → EXECUTING is INVALID (terminal state)."""
        engine = SemanticGuardEngine()
        history = ("CREATED", "APPROVED", "EXECUTING", "FAILED")
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="FAILED",
            next_state="EXECUTING",
            history=history,
        )
        
        assert result is not None, "FAILED → EXECUTING should be invalid"
        assert result.violation_type == SemanticTransitionViolation.TERMINAL_STATE_TRANSITION
    
    def test_completed_to_executing_invalid(self):
        """COMPLETED → EXECUTING is INVALID (terminal state)."""
        engine = SemanticGuardEngine()
        history = ("CREATED", "APPROVED", "EXECUTING", "COMPLETED")
        
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="COMPLETED",
            next_state="EXECUTING",
            history=history,
        )
        
        assert result is not None, "COMPLETED → EXECUTING should be invalid"
        assert result.violation_type == SemanticTransitionViolation.TERMINAL_STATE_TRANSITION


class TestHiddenStateDetection:
    """Test detection of hidden states (not in lineage but in history)."""
    
    def test_hidden_state_synthetic_injection(self):
        """Detect when state is synthesized (not in recorded lineage)."""
        engine = SemanticGuardEngine()
        
        # History has EXECUTING but path skipped APPROVED
        history = ("CREATED", "EXECUTING")
        
        result = engine.validate_state_history(
            execution_id="exec_1",
            history=history,
        )
        
        assert result is not None, "Should detect hidden/synthetic state"
        assert result.violation_type == SemanticTransitionViolation.SYNTHETIC_STATE_INJECTED
        assert "APPROVED" in result.missing_states
    
    def test_history_must_start_with_created(self):
        """History must start with CREATED."""
        engine = SemanticGuardEngine()
        
        history = ("APPROVED", "EXECUTING", "COMPLETED")
        
        result = engine.validate_state_history(
            execution_id="exec_1",
            history=history,
        )
        
        assert result is not None, "Should reject history not starting with CREATED"
        assert result.violation_type == SemanticTransitionViolation.HIDDEN_STATE_DETECTED
    
    def test_lineage_event_missing(self):
        """Detect when lineage event is missing for a state."""
        engine = SemanticGuardEngine()
        
        history = ("CREATED", "APPROVED", "EXECUTING", "COMPLETED")
        lineage_events = [
            {"state": "CREATED", "event_id": "e1"},
            {"state": "APPROVED", "event_id": "e2"},
            # EXECUTING missing!
            {"state": "COMPLETED", "event_id": "e4"},
        ]
        
        result = engine.validate_state_history(
            execution_id="exec_1",
            history=history,
            lineage_events=lineage_events,
        )
        
        assert result is not None, "Should detect missing lineage event"
        assert result.violation_type == SemanticTransitionViolation.HIDDEN_STATE_DETECTED
        assert "EXECUTING" in result.missing_states


class TestGovernanceStateCoupling:
    """Test governance-state coupling validation."""
    
    def test_governance_state_must_be_sufficient(self):
        """Governance state must be at or above execution state precedence."""
        engine = SemanticGuardEngine()
        
        history = ("CREATED", "APPROVED")
        
        # Attempt EXECUTING with only CREATED governance (insufficient)
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="APPROVED",
            next_state="EXECUTING",
            history=history,
            governance_state="CREATED",  # Insufficient
        )
        
        assert result is not None, "Governance state must be sufficient"
        assert result.violation_type == SemanticTransitionViolation.GOVERNANCE_STATE_VIOLATION
    
    def test_governance_state_sufficient(self):
        """Governance state can match execution state."""
        engine = SemanticGuardEngine()
        
        history = ("CREATED", "APPROVED")
        
        # EXECUTING with APPROVED governance is ok
        result = engine.validate_transition(
            execution_id="exec_1",
            current_state="APPROVED",
            next_state="EXECUTING",
            history=history,
            governance_state="APPROVED",  # Sufficient
        )
        
        assert result is None, "Governance state APPROVED is sufficient for EXECUTING"


class TestReplayChainValidation:
    """Test validation of replay chains from lineage."""
    
    def test_valid_replay_chain(self):
        """Valid replay chain should pass validation."""
        engine = SemanticGuardEngine()
        
        replay_events = [
            {"state": "CREATED", "trace_hash": "h1", "timestamp": 1000},
            {"state": "APPROVED", "trace_hash": "h2", "timestamp": 1001},
            {"state": "EXECUTING", "trace_hash": "h3", "timestamp": 1002},
            {"state": "COMPLETED", "trace_hash": "h4", "timestamp": 1003},
        ]
        
        result = engine.validate_replay_chain(
            execution_id="exec_1",
            replay_events=replay_events,
        )
        
        assert result is None, "Valid replay chain should pass"
    
    def test_replay_chain_with_gap(self):
        """Replay chain with missing state should fail."""
        engine = SemanticGuardEngine()
        
        replay_events = [
            {"state": "CREATED", "trace_hash": "h1", "timestamp": 1000},
            {"state": "APPROVED", "trace_hash": "h2", "timestamp": 1001},
            # EXECUTING missing
            {"state": "COMPLETED", "trace_hash": "h4", "timestamp": 1003},
        ]
        
        result = engine.validate_replay_chain(
            execution_id="exec_1",
            replay_events=replay_events,
        )
        
        assert result is not None, "Replay chain with gap should fail"
        assert result.violation_type == SemanticTransitionViolation.SYNTHETIC_STATE_INJECTED
    
    def test_replay_chain_invalid_transition(self):
        """Replay chain with invalid transition should fail."""
        engine = SemanticGuardEngine()
        
        replay_events = [
            {"state": "CREATED", "trace_hash": "h1", "timestamp": 1000},
            # Invalid: skip APPROVED
            {"state": "EXECUTING", "trace_hash": "h3", "timestamp": 1002},
        ]
        
        result = engine.validate_replay_chain(
            execution_id="exec_1",
            replay_events=replay_events,
        )
        
        assert result is not None, "Replay chain with invalid transition should fail"


class TestPublicAPIFunctions:
    """Test the public API functions."""
    
    def test_validate_state_transition_api(self):
        """Test validate_state_transition() public function."""
        history = ("CREATED", "APPROVED")
        
        # Valid transition should not raise
        validate_state_transition(
            execution_id="exec_1",
            current_state="APPROVED",
            next_state="EXECUTING",
            history=history,
        )
    
    def test_validate_state_transition_api_invalid(self):
        """Test validate_state_transition() rejects invalid transitions."""
        history = ("CREATED",)
        
        with pytest.raises(ValueError) as exc_info:
            validate_state_transition(
                execution_id="exec_1",
                current_state="CREATED",
                next_state="COMPLETED",
                history=history,
            )
        
        assert "exec_1" in str(exc_info.value)
        assert "COMPLETED" in str(exc_info.value)
    
    def test_validate_state_history_api(self):
        """Test validate_state_history() public function."""
        history = ("CREATED", "APPROVED", "EXECUTING", "COMPLETED")
        
        # Valid history should not raise
        validate_state_history(
            execution_id="exec_1",
            history=history,
        )
    
    def test_validate_state_history_api_invalid(self):
        """Test validate_state_history() detects hidden states."""
        history = ("CREATED", "EXECUTING")  # Missing APPROVED
        
        with pytest.raises(ValueError) as exc_info:
            validate_state_history(
                execution_id="exec_1",
                history=history,
            )
        
        assert "exec_1" in str(exc_info.value)
        assert "APPROVED" in str(exc_info.value)
    
    def test_validate_replay_chain_api(self):
        """Test validate_replay_chain() public function."""
        replay_events = [
            {"state": "CREATED", "trace_hash": "h1"},
            {"state": "APPROVED", "trace_hash": "h2"},
            {"state": "EXECUTING", "trace_hash": "h3"},
            {"state": "COMPLETED", "trace_hash": "h4"},
        ]
        
        # Valid replay should not raise
        validate_replay_chain(
            execution_id="exec_1",
            replay_events=replay_events,
        )


class TestViolationReports:
    """Test semantic violation report generation."""
    
    def test_violation_report_to_dict(self):
        """Violation reports should convert to dict for logging."""
        report = SemanticViolationReport(
            violation_type=SemanticTransitionViolation.STATE_PREREQUISITE_MISSING,
            execution_id="exec_1",
            current_state="CREATED",
            attempted_state="COMPLETED",
            reason="Missing prerequisites",
            missing_states={"APPROVED", "EXECUTING"},
        )
        
        report_dict = report.to_dict()
        assert report_dict["violation_type"] == "state_prerequisite_missing"
        assert report_dict["execution_id"] == "exec_1"
        assert "APPROVED" in report_dict["missing_states"]
    
    def test_explain_violation(self):
        """Violation explanations should be human-readable."""
        engine = SemanticGuardEngine()
        
        report = SemanticViolationReport(
            violation_type=SemanticTransitionViolation.STATE_PREREQUISITE_MISSING,
            execution_id="exec_1",
            current_state="CREATED",
            attempted_state="COMPLETED",
            reason="Missing prerequisites",
            missing_states={"APPROVED", "EXECUTING"},
            actual_sequence=["CREATED"],
        )
        
        explanation = engine.explain_violation(report)
        assert "SEMANTIC VIOLATION" in explanation
        assert "exec_1" in explanation
        assert "CREATED" in explanation
        assert "COMPLETED" in explanation


class TestSemanticGuardSingleton:
    """Test the semantic guard engine singleton."""
    
    def test_get_semantic_guard(self):
        """Get semantic guard should return singleton."""
        guard1 = get_semantic_guard()
        guard2 = get_semantic_guard()
        
        assert guard1 is guard2, "Should return same instance"
        assert isinstance(guard1, SemanticGuardEngine)


if __name__ == "__main__":
    # Run tests with: pytest tests/test_phase4_semantic_guards.py -v
    pytest.main([__file__, "-v"])
