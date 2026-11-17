from typing import Any, Dict, Literal

from pydantic import BaseModel, field_validator


SUPPORTED_DECISION_VERSIONS = {
    "v1",
}


ALLOWED_ACTIONS = {
    "restart",
    "scale_up",
    "scale_down",
    "rollback",
    "noop",
}


class DecisionContract(BaseModel):
    decision_type: Literal["execution", "abstention", "action_request_eligible"]
    action: str
    parameters: Dict[str, Any]
    version: str

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value not in SUPPORTED_DECISION_VERSIONS:
            raise ValueError(f"Unsupported decision version: {value}")
        return value

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported action: {value}")
        return value


def validate_decision_contract(payload: dict) -> DecisionContract:
    return DecisionContract(**payload)