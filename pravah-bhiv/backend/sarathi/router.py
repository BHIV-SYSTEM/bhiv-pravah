from security.internal_requests import build_signed_headers

SERVICE_ID = "sarathi"


def build_sarathi_headers(payload: dict):
    headers = build_signed_headers(SERVICE_ID, payload)
    print(f"[SERVICE_ID={SERVICE_ID}] signed request prepared")
    return headers


def attach_sarathi_header(payload: dict):
    return build_sarathi_headers(payload)