import os
import time
import uuid

import requests

from security.signing import (
    sign_service_request
)


SERVICE_ID = os.getenv("SERVICE_ID", "control-plane")


def build_signed_headers(
    service_id: str,
    payload: dict,
):

    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())

    signature = sign_service_request(
        service_id=service_id,
        timestamp=timestamp,
        nonce=nonce,
        payload_dict=payload
    )

    return {
        "X-Service-Id": service_id,
        "X-Service-Timestamp": timestamp,
        "X-Service-Nonce": nonce,
        "X-Service-Signature": signature,
    }


def signed_post(
    url: str,
    payload: dict,
    timeout: int = 10
):
    headers = build_signed_headers(SERVICE_ID, payload)

    return requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout
    )