import sqlite3

from src.cyberattacks import api_client
from src.cyberattacks import world_bank_client
from src.cyberattacks.database import (
    initialize_database,
    insert_api_records,
    insert_csv_records,
)


def test_verify_cloudflare_token(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True, "result": {}}

    captured = {}

    def fake_get(url, *, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    result = api_client.verify_cloudflare_token("token-value", timeout_seconds=12)

    assert result["success"] is True
    assert captured == {
        "url": "https://api.cloudflare.com/client/v4/user/tokens/verify",
        "headers": {"Authorization": "Bearer token-value"},
        "timeout": 12,
    }


def test_fetch_records_supports_cloudflare_result_object(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True, "result": {"summary": {"total": 3}}}

    captured = {}

    def fake_get(url, *, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    records = api_client.fetch_records(
        "https://api.cloudflare.com/client/v4/radar/attacks/layer7/summary",
        token="token-value",
    )

    assert records == [{"summary": {"total": 3}}]
    assert captured["headers"] == {"Authorization": "Bearer token-value"}


def test_fetch_records_flattens_cloudflare_top_attacks(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "success": True,
                "result": {
                    "top_0": [
                        {"rank": 1, "originCountryName": "China"},
                        {"rank": 2, "originCountryName": "United States"},
                    ],
                    "meta": {"dateRange": "1d"},
                },
            }

    monkeypatch.setattr(
        api_client.requests,
        "get",
        lambda *args, **kwargs: Response(),
    )

    records = api_client.fetch_records(
        "https://api.cloudflare.com/client/v4/radar/attacks/layer7/top/attacks",
        token="token-value",
    )

    assert records == [
        {"rank": 1, "originCountryName": "China"},
        {"rank": 2, "originCountryName": "United States"},
    ]


def test_fetch_world_bank_indicator(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"page": 1},
                [{"date": "2024", "value": 7, "country": {"value": "Thailand"}}],
            ]

    captured = {}
    current_url = {}

    class ContextResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b""

    def fake_urlopen(request, timeout):
        captured.update(url=request.full_url, timeout=timeout)
        current_url["value"] = request.full_url
        return ContextResponse()

    def fake_json_load(response):
        if "/country?" in current_url["value"]:
            return [{"pages": 1}, [{"id": "THA"}]]
        return [
            {"page": 1, "pages": 1},
            [{"date": "2024", "value": 7, "country": {"value": "Thailand"}}],
        ]

    monkeypatch.setattr(world_bank_client, "urlopen", fake_urlopen)
    monkeypatch.setattr(world_bank_client.json, "load", fake_json_load)

    records = world_bank_client.fetch_indicator(
        "https://api.worldbank.org/v2/country/all",
        "TEST.INDICATOR",
        country_limit=1,
    )

    assert records[0]["value"] == 7
    assert captured["url"] == (
        "https://api.worldbank.org/v2/country/THA/indicator/"
        "TEST.INDICATOR?date=2022:2024&format=json"
    )


def test_insert_api_and_csv_records(tmp_path):
    database_path = tmp_path / "cyberattacks.db"
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text(
        """
        CREATE TABLE api_cyberattacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            payload TEXT,
            ingested_at TEXT
        );
        CREATE TABLE csv_cyberattacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_type TEXT,
            description TEXT,
            source TEXT,
            occurred_at TEXT,
            ingested_at TEXT
        );
        """,
        encoding="utf-8",
    )

    initialize_database(str(database_path), str(schema_path))
    insert_api_records(str(database_path), "https://example.test", [{"id": 1}], "now")
    insert_csv_records(
        str(database_path),
        [{"attack_type": "Phishing", "description": "test"}],
        "now",
    )

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM api_cyberattacks").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM csv_cyberattacks").fetchone()[0] == 1
