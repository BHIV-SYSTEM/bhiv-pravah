"""
Execution State Type Definition

Shared type definition to avoid circular imports.
"""

from typing import Literal

ExecutionState = Literal["CREATED", "APPROVED", "EXECUTED", "COMPLETED", "FAILED"]
