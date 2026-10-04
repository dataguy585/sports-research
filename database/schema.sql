CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieved_at TEXT NOT NULL,
    source TEXT NOT NULL,
    sport TEXT,
    market TEXT,
    status TEXT NOT NULL,
    http_status INTEGER,
    event_count INTEGER,
    bookmaker_count INTEGER,
    requests_remaining INTEGER,
    requests_used INTEGER,
    requests_last INTEGER,
    snapshot_path TEXT,
    payload_sha256 TEXT,
    error_message TEXT
);
