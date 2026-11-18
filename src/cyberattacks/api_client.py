from __future__ import annotations

from typing import Any

import requests


def verify_cloudflare_token(
    token: str,
    timeout_seconds: int = 30,
    verify_url: str = "https://api.cloudflare.com/client/v4/user/tokens/verify",
) -> dict[str, Any]:
    """Verify a Cloudflare API token without exposing it in logs or URLs."""
    if not token.strip():
        raise ValueError("Cloudflare API token must not be empty")

    response = requests.get(
        verify_url,
        headers={"Authorization": "Bearer " + token},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("Cloudflare token verification was not successful")
    return payload


def fetch_records(
    url: str,
    timeout_seconds: int = 30,
    token: str | None = None,
) -> list[dict[str, Any]]:
    headers = {"Authorization": "Bearer " + token} if token else {}
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        if payload.get("success") is False:
            raise ValueError("API request was not successful")
        if isinstance(payload.get("data"), list):
            records = payload["data"]
        elif isinstance(payload.get("result"), list):
            records = payload["result"]
        elif isinstance(payload.get("result"), dict):
            result = payload["result"]
            list_values = [
                value for value in result.values() if isinstance(value, list)
            ]
            records = [record for values in list_values for record in values]
            if not records:
                records = [result]
        else:
            raise ValueError(
                "API response must contain a list in 'data' or 'result', "
                "or an object in 'result'"
            )
    else:
        raise ValueError("API response must be a JSON list or object")

    if not all(isinstance(record, dict) for record in records):
        raise ValueError("Every API record must be a JSON object")
    return records
