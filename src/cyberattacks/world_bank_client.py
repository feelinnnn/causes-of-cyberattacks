from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)

def _get_json(url: str, timeout_seconds: int) -> Any:
    last_error: Exception | None = None
    for attempt, delay in enumerate((2, 4, 8)):
        if delay:
            time.sleep(delay)
        try:
            request = Request(url, headers={"User-Agent": "cyberattacks-ingestion/1.0"})
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.load(response)
        except Exception as error:
            last_error = error
            if attempt == 2:
                raise
    raise RuntimeError("World Bank request failed") from last_error


def _indicator_endpoint(url: str, indicator: str, country: str = "") -> str:
    endpoint = url.rstrip("/")
    if not endpoint.endswith("/indicator"):
        endpoint = f"{endpoint}/indicator"
    if country:
        endpoint = endpoint.replace("/country/all/", f"/country/{country}/")
    return (
        f"{endpoint}/{quote(indicator, safe='')}"
        "?date={date}&format=json"
    )


def fetch_indicator(
    url: str,
    indicator: str,
    date_range: str = "2022:2024",
    timeout_seconds: int = 30,
    country_limit: int = 50,
) -> list[dict[str, Any]]:
    if not indicator.strip():
        raise ValueError("WORLD_BANK_INDICATOR is required")

    country_url = url.rstrip("/")
    if country_url.endswith("/indicator"):
        country_url = country_url[: -len("/indicator")]
    countries_payload = _get_json(
        f"{country_url.replace('/country/all', '/country')}?format=json&per_page={country_limit * 2}",
        timeout_seconds,
    )
    if (
        not isinstance(countries_payload, list)
        or len(countries_payload) < 2
        or not isinstance(countries_payload[1], list)
    ):
        raise ValueError("World Bank country list response is invalid")

    countries = [
        country
        for country in countries_payload[1]
        if isinstance(country, dict)
        and country.get("region", {}).get("id") not in {"NA", "NAF"}
    ][:country_limit]

    def fetch_country(country: Any) -> list[dict[str, Any]]:
        code = country.get("id") if isinstance(country, dict) else None
        if not code:
            return []
        endpoint = _indicator_endpoint(url, indicator, quote(str(code), safe=""))
        try:
            payload = _get_json(
                endpoint.format(date=quote(date_range, safe=":")),
                timeout_seconds,
            )
        except Exception as error:
            LOGGER.warning("Skipping World Bank country %s: %s", code, error)
            return []
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            LOGGER.warning("Skipping World Bank country %s: invalid response", code)
            return []
        return [record for record in payload[1] if isinstance(record, dict)]

    with ThreadPoolExecutor(max_workers=5) as executor:
        country_records = executor.map(fetch_country, countries)
        records = [record for country_rows in country_records for record in country_rows]

    if records:
        return records

    fallback = _get_json(
        f"{_indicator_endpoint(url, indicator).format(date=quote(date_range, safe=':'))}"
        f"&page=1&per_page={country_limit}",
        timeout_seconds,
    )
    if not isinstance(fallback, list) or len(fallback) < 2 or not isinstance(fallback[1], list):
        raise ValueError(f"World Bank fallback response is invalid for {indicator}")
    return [record for record in fallback[1] if isinstance(record, dict)]
