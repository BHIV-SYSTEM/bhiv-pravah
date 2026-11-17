from flask import request

from security.signing import (
    verify_service_request
)

from security.nonce_store import (
    check_nonce
)


SERVICE_ID_HEADER = "X-Service-Id"
SERVICE_TIMESTAMP_HEADER = "X-Service-Timestamp"
SERVICE_NONCE_HEADER = "X-Service-Nonce"
SERVICE_SIGNATURE_HEADER = "X-Service-Signature"


class ServiceAuthError(Exception):
    pass


def verify_service_auth(payload: dict):

    if not isinstance(payload, dict):
        raise ServiceAuthError("Payload must be an object")

    service_id = request.headers.get(
        SERVICE_ID_HEADER
    )

    timestamp = request.headers.get(
        SERVICE_TIMESTAMP_HEADER
    )

    nonce = request.headers.get(
        SERVICE_NONCE_HEADER
    )

    signature = request.headers.get(
        SERVICE_SIGNATURE_HEADER
    )

    if not service_id:
        raise ServiceAuthError(
            "Missing service id"
        )

    if not timestamp:
        raise ServiceAuthError(
            "Missing timestamp"
        )

    if not nonce:
        raise ServiceAuthError(
            "Missing nonce"
        )

    if not signature:
        raise ServiceAuthError(
            "Missing service signature"
        )

    body_service_id = payload.get("service_id")
    if body_service_id and body_service_id != service_id and service_id != "sarathi":
        raise ServiceAuthError(
            "Service identity mismatch"
        )

    if not check_nonce(nonce):
        raise ServiceAuthError(
            "Replay attack detected"
        )

    verified = verify_service_request(
        service_id=service_id,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        payload_dict=payload
    )

    if not verified:
        raise ServiceAuthError(
            "Invalid service signature"
        )

    payload["verified_service_id"] = (
        service_id
    )

    return payload