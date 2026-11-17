from security.nonce_store import check_nonce
from security.signing import verify_service_request
from contracts.execution_contract import validate_execution_contract


SERVICE_ID = "sarathi"
SERVICE_ID_HEADER = "X-Service-Id"
SERVICE_TIMESTAMP_HEADER = "X-Service-Timestamp"
SERVICE_NONCE_HEADER = "X-Service-Nonce"
SERVICE_SIGNATURE_HEADER = "X-Service-Signature"


def validate_caller(payload: dict, headers: dict):
    payload_copy = dict(payload)
    service_id = headers.get(SERVICE_ID_HEADER)
    timestamp = headers.get(SERVICE_TIMESTAMP_HEADER)
    nonce = headers.get(SERVICE_NONCE_HEADER)
    signature = headers.get(SERVICE_SIGNATURE_HEADER)

    if service_id != SERVICE_ID:
        print(f"[SERVICE_ID={service_id or 'missing'}] rejected: 403")
        raise PermissionError("403 Forbidden: Only Sarathi can call Executer")

    if not timestamp:
        raise PermissionError("403 Forbidden: Missing service timestamp")

    if not nonce:
        raise PermissionError("403 Forbidden: Missing service nonce")

    if not signature:
        raise PermissionError("403 Forbidden: Missing service signature")

    if not check_nonce(nonce):
        raise PermissionError("403 Forbidden: Replay attack detected")

    if not verify_service_request(
        service_id=service_id,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        payload_dict=payload_copy,
    ):
        raise PermissionError("403 Forbidden: Invalid service signature")

    execution_contract = payload_copy.get("execution_contract")
    if execution_contract:
        try:
            validate_execution_contract(execution_contract, payload_copy)
        except Exception as exc:
            raise PermissionError(f"403 Forbidden: Invalid execution contract: {exc}")
    else:
        raise PermissionError("403 Forbidden: Missing execution contract")

    payload_copy["verified_service_id"] = service_id
    print(f"[SERVICE_ID={SERVICE_ID}] accepted")
    return payload_copy