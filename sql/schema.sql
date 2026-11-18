CREATE TABLE IF NOT EXISTS api_cyberattacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    payload TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS csv_cyberattacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attack_type TEXT,
    description TEXT,
    source TEXT,
    occurred_at TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_csv_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    payload TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS world_bank_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator TEXT NOT NULL,
    country_id TEXT,
    country_name TEXT,
    year TEXT,
    value TEXT,
    payload TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);
