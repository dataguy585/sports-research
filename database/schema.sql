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


CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_run_id INTEGER NOT NULL,
    snapshot_time TEXT NOT NULL,
    event_id TEXT NOT NULL,
    commence_time TEXT,
    home_team TEXT,
    away_team TEXT,
    sportsbook_key TEXT NOT NULL,
    sportsbook_name TEXT,
    market_key TEXT NOT NULL,
    outcome_name TEXT NOT NULL,
    price REAL,
    point REAL,
    last_update TEXT,
    FOREIGN KEY (collection_run_id)
        REFERENCES collection_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_odds_event
ON odds_snapshots(event_id);

CREATE INDEX IF NOT EXISTS idx_odds_sportsbook
ON odds_snapshots(sportsbook_key);

CREATE INDEX IF NOT EXISTS idx_odds_snapshot_time
ON odds_snapshots(snapshot_time);

CREATE UNIQUE INDEX IF NOT EXISTS idx_odds_unique_snapshot
ON odds_snapshots (
    collection_run_id,
    event_id,
    sportsbook_key,
    market_key,
    outcome_name
);
CREATE TABLE IF NOT EXISTS market_benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_run_id INTEGER NOT NULL,
    snapshot_time TEXT NOT NULL,
    event_id TEXT NOT NULL,
    home_team TEXT,
    away_team TEXT,
    outcome_name TEXT NOT NULL,
    consensus_probability REAL NOT NULL,
    sportsbook_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (collection_run_id)
        REFERENCES collection_runs(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_benchmark_unique
ON market_benchmarks (
    collection_run_id,
    event_id,
    outcome_name
);

CREATE INDEX IF NOT EXISTS idx_market_benchmark_event
ON market_benchmarks(event_id);

CREATE INDEX IF NOT EXISTS idx_market_benchmark_snapshot
ON market_benchmarks(snapshot_time);

CREATE TABLE IF NOT EXISTS game_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport TEXT NOT NULL,
    event_id TEXT NOT NULL,
    commence_time TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    status TEXT NOT NULL,
    winner TEXT,
    completed_at TEXT,
    retrieved_at TEXT NOT NULL,
    source TEXT NOT NULL,
    source_payload_sha256 TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_game_results_unique
ON game_results (
    sport,
    event_id
);

CREATE INDEX IF NOT EXISTS idx_game_results_sport
ON game_results(sport);

CREATE INDEX IF NOT EXISTS idx_game_results_status
ON game_results(status);

CREATE INDEX IF NOT EXISTS idx_game_results_commence_time
ON game_results(commence_time);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    sport TEXT NOT NULL,
    collection_run_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    commence_time TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,

    market_key TEXT NOT NULL,
    outcome_name TEXT NOT NULL,
    sportsbook_key TEXT,
    offered_price REAL,

    market_probability REAL,
    model_probability REAL,
    model_edge REAL,

    decision TEXT NOT NULL,
    stake_units REAL,

    model_version TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    reason TEXT,

    settled_status TEXT DEFAULT 'UNSETTLED',
    result TEXT,
    profit_units REAL,

    FOREIGN KEY (collection_run_id)
        REFERENCES collection_runs(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_unique_model_run
ON decisions (
    collection_run_id,
    event_id,
    market_key,
    outcome_name,
    model_version,
    rule_version
);

CREATE INDEX IF NOT EXISTS idx_decisions_event
ON decisions(event_id);

CREATE INDEX IF NOT EXISTS idx_decisions_sport
ON decisions(sport);

CREATE INDEX IF NOT EXISTS idx_decisions_collection_run
ON decisions(collection_run_id);

CREATE INDEX IF NOT EXISTS idx_decisions_status
ON decisions(decision);

CREATE INDEX IF NOT EXISTS idx_decisions_settlement
ON decisions(settled_status);
