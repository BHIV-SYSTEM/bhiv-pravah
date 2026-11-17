"""
Tests for Phase 4 Semantic Transition Validation

These tests verify that the system correctly rejects transitions that are
syntactically valid (allowed by the FSM) but semantically invalid (missing
required prerequisite states in the execution history).
"""

import pytest
from contracts.semantic_transition_validator import (
    validate_semantic_transition,
    validate_semantic_transition_with_context,
    SEMANTIC_PREREQUISITES,
    explain_semantic_rules,
)


class TestSemanticTransitionValidation:
    """Test semantic transition validation rules."""
    
    def test_valid_path_created_approved(self):
        """CREATED → APPROVED is valid (CREATED is prerequisite)."""
        history = ("CREATED",)
        # Should not raise
        validate_semantic_transition(
            current_state="CREATED",
            next_state="APPROVED",
            history=history,
        )
    
    def test_valid_path_approved_executed(self):
        """APPROVED → EXECUTED is valid (requires CREATED, APPROVED in history)."""
        history = ("CREATED", "APPROVED")
        # Should not raise
        validate_semantic_transition(
            current_state="APPROVED",
            next_state="EXECUTED",
            history=history,
        )
    
    def test_valid_path_executed_completed(self):
        """EXECUTED → COMPLETED is valid (requires CREATED, APPROVED, EXECUTED)."""
        history = ("CREATED", "APPROVED", "EXECUTED")
        # Should not raise
        validate_semantic_transition(
            current_state="EXECUTED",
            next_state="COMPLETED",
            history=history,
        )
    
    def test_valid_full_execution_path(self):
        """Full valid path: CREATED → APPROVED → EXECUTED → COMPLETED."""
        # Test each step
        history = ("CREATED",)
        validate_semantic_transition("CREATED", "APPROVED", history)
        
        history = ("CREATED", "APPROVED")
        validate_semantic_transition("APPROVED", "EXECUTED", history)
        
        history = ("CREATED", "APPROVED", "EXECUTED")
        validate_semantic_transition("EXECUTED", "COMPLETED", history)
    
    def test_invalid_created_to_completed(self):
        """CREATED → COMPLETED is INVALID (missing APPROVED and EXECUTED)."""
        history = ("CREATED",)
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="CREATED",
                next_state="COMPLETED",
                history=history,
            )
        assert "COMPLETED" in str(exc_info.value)
        assert "APPROVED" in str(exc_info.value)
        assert "EXECUTED" in str(exc_info.value)
    
    def test_invalid_created_to_executed(self):
        """CREATED → EXECUTED is INVALID (missing APPROVED)."""
        history = ("CREATED",)
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="CREATED",
                next_state="EXECUTED",
                history=history,
            )
        assert "EXECUTED" in str(exc_info.value)
        assert "APPROVED" in str(exc_info.value)
    
    def test_invalid_approved_to_completed(self):
        """APPROVED → COMPLETED is INVALID (missing EXECUTED)."""
        history = ("CREATED", "APPROVED")
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="APPROVED",
                next_state="COMPLETED",
                history=history,
            )
        assert "COMPLETED" in str(exc_info.value)
        assert "EXECUTED" in str(exc_info.value)
    
    def test_valid_failure_from_created(self):
        """CREATED → FAILED is valid (CREATED is prerequisite for FAILED)."""
        history = ("CREATED",)
        # Should not raise
        validate_semantic_transition(
            current_state="CREATED",
            next_state="FAILED",
            history=history,
        )
    
    def test_valid_failure_from_approved(self):
        """APPROVED → FAILED is valid (has CREATED and APPROVED)."""
        history = ("CREATED", "APPROVED")
        # Should not raise
        validate_semantic_transition(
            current_state="APPROVED",
            next_state="FAILED",
            history=history,
        )
    
    def test_valid_failure_from_executed(self):
        """EXECUTED → FAILED is valid (has all prerequisites)."""
        history = ("CREATED", "APPROVED", "EXECUTED")
        # Should not raise
        validate_semantic_transition(
            current_state="EXECUTED",
            next_state="FAILED",
            history=history,
        )
    
    def test_empty_history_raises_error(self):
        """Empty history should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="CREATED",
                next_state="APPROVED",
                history=(),
            )
        assert "cannot be empty" in str(exc_info.value).lower()
    
    def test_semantic_validation_with_context(self):
        """Semantic validation with execution_id context."""
        history = ("CREATED",)
        execution_id = "test_exec_123"
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition_with_context(
                current_state="CREATED",
                next_state="COMPLETED",
                history=history,
                execution_id=execution_id,
            )
        assert execution_id in str(exc_info.value)
    
    def test_prerequisites_mapping(self):
        """Verify semantic prerequisites mapping is correctly defined."""
        # CREATED has no prerequisites
        assert SEMANTIC_PREREQUISITES["CREATED"] == set()
        
        # APPROVED requires CREATED
        assert SEMANTIC_PREREQUISITES["APPROVED"] == {"CREATED"}
        
        # EXECUTED requires CREATED and APPROVED
        assert SEMANTIC_PREREQUISITES["EXECUTED"] == {"CREATED", "APPROVED"}
        
        # COMPLETED requires full path
        assert SEMANTIC_PREREQUISITES["COMPLETED"] == {"CREATED", "APPROVED", "EXECUTED"}
        
        # FAILED only requires CREATED
        assert SEMANTIC_PREREQUISITES["FAILED"] == {"CREATED"}


class TestSemanticTransitionPatterns:
    """Test common semantic transition patterns and edge cases."""
    
    def test_multiple_approval_attempts(self):
        """Multiple transitions through same state should be allowed."""
        # Though FSM might not allow A → A → A, semantically it's fine
        # This tests if history check works with repeated checks
        history = ("CREATED", "APPROVED")
        # APPROVED can try to execute
        validate_semantic_transition("APPROVED", "EXECUTED", history)
    
    def test_failure_before_approval(self):
        """System can fail during creation (before approval)."""
        history = ("CREATED",)
        validate_semantic_transition("CREATED", "FAILED", history)
    
    def test_failure_after_approval(self):
        """System can fail after approval but before execution."""
        history = ("CREATED", "APPROVED")
        validate_semantic_transition("APPROVED", "FAILED", history)
    
    def test_failure_after_execution(self):
        """System can fail during or after execution."""
        history = ("CREATED", "APPROVED", "EXECUTED")
        validate_semantic_transition("EXECUTED", "FAILED", history)


class TestSemanticTransitionErrorMessages:
    """Test that error messages are clear and actionable."""
    
    def test_error_message_includes_history(self):
        """Error message should show the actual history."""
        history = ("CREATED",)
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="CREATED",
                next_state="COMPLETED",
                history=history,
            )
        error_msg = str(exc_info.value)
        assert "CREATED" in error_msg
        assert "COMPLETED" in error_msg
    
    def test_error_message_includes_missing_states(self):
        """Error message should specify which prerequisite states are missing."""
        history = ("CREATED",)
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="CREATED",
                next_state="EXECUTED",
                history=history,
            )
        error_msg = str(exc_info.value)
        assert "APPROVED" in error_msg
        assert "missing" in error_msg.lower()
    
    def test_error_explains_semantic_meaning(self):
        """Error message should explain the semantic meaning."""
        history = ("CREATED", "APPROVED")
        with pytest.raises(ValueError) as exc_info:
            validate_semantic_transition(
                current_state="APPROVED",
                next_state="COMPLETED",
                history=history,
            )
        error_msg = str(exc_info.value)
        # Should explain why this transition is invalid
        assert "semantic" in error_msg.lower() or "requires" in error_msg.lower() or "must" in error_msg.lower()


class TestSemanticRulesExplanation:
    """Test the semantic rules explanation function."""
    
    def test_explain_semantic_rules(self):
        """Explain semantic rules function should return readable text."""
        explanation = explain_semantic_rules()
        assert isinstance(explanation, str)
        assert "PHASE 4" in explanation
        assert "SEMANTIC" in explanation
        assert "CREATED" in explanation
        assert "APPROVED" in explanation
        assert "EXECUTED" in explanation
        assert "COMPLETED" in explanation
    
    def test_explanation_includes_valid_transitions(self):
        """Explanation should include examples of valid transitions."""
        explanation = explain_semantic_rules()
        assert "CREATED" in explanation
        assert "APPROVED" in explanation
        assert "EXECUTED" in explanation
        assert "COMPLETED" in explanation
    
    def test_explanation_includes_invalid_transitions(self):
        """Explanation should include examples of invalid transitions."""
        explanation = explain_semantic_rules()
        assert "INVALID" in explanation or "invalid" in explanation.lower()


if __name__ == "__main__":
    # Run tests with: pytest tests/test_semantic_transition_validator.py -v
    pytest.main([__file__, "-v"])
