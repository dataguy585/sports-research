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

CREATE TABLE IF NOT EXISTS injury_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieved_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    expected_week INTEGER NOT NULL,
    latest_week INTEGER,
    status TEXT NOT NULL,
    row_count INTEGER,
    source TEXT NOT NULL,
    snapshot_path TEXT,
    payload_sha256 TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_injury_snapshots_season_week
ON injury_snapshots (
    season,
    expected_week,
    retrieved_at
);

CREATE INDEX IF NOT EXISTS idx_injury_snapshots_status
ON injury_snapshots(status);


CREATE TABLE IF NOT EXISTS nfl_injuries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    injury_snapshot_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    season_type TEXT,
    game_type TEXT,
    team TEXT NOT NULL,
    week INTEGER NOT NULL,
    gsis_id TEXT,
    position TEXT,
    full_name TEXT,
    first_name TEXT,
    last_name TEXT,
    report_primary_injury TEXT,
    report_secondary_injury TEXT,
    report_status TEXT,
    practice_primary_injury TEXT,
    practice_secondary_injury TEXT,
    practice_status TEXT,

    FOREIGN KEY (injury_snapshot_id)
        REFERENCES injury_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_nfl_injuries_snapshot
ON nfl_injuries(injury_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_nfl_injuries_team_week
ON nfl_injuries (
    season,
    week,
    team
);

CREATE INDEX IF NOT EXISTS idx_nfl_injuries_player
ON nfl_injuries(gsis_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_nfl_injuries_unique_snapshot
ON nfl_injuries (
    injury_snapshot_id,
    season,
    week,
    team,
    gsis_id
);
CREATE TABLE IF NOT EXISTS efficiency_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieved_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    through_week INTEGER NOT NULL,
    source_latest_week INTEGER NOT NULL,
    status TEXT NOT NULL,
    play_count INTEGER,
    team_count INTEGER,
    source TEXT NOT NULL,
    snapshot_path TEXT,
    payload_sha256 TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_efficiency_snapshots_season_week
ON efficiency_snapshots (
    season,
    through_week,
    retrieved_at
);

CREATE INDEX IF NOT EXISTS idx_efficiency_snapshots_status
ON efficiency_snapshots(status);


CREATE TABLE IF NOT EXISTS team_efficiency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    efficiency_snapshot_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    through_week INTEGER NOT NULL,
    team TEXT NOT NULL,

    off_epa_per_play REAL,
    def_epa_per_play REAL,

    off_success_rate REAL,
    def_success_rate REAL,

    dropback_epa_per_play REAL,
    rush_epa_per_play REAL,

    off_plays INTEGER,
    def_plays INTEGER,
    recent_games INTEGER,

    recent_off_epa_per_play REAL,
    recent_def_epa_per_play REAL,

    recent_off_success_rate REAL,
    recent_def_success_rate REAL,

    recent_dropback_epa_per_play REAL,
    recent_rush_epa_per_play REAL,
    FOREIGN KEY (efficiency_snapshot_id)
        REFERENCES efficiency_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_team_efficiency_snapshot
ON team_efficiency(efficiency_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_team_efficiency_team
ON team_efficiency (
    season,
    through_week,
    team
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_team_efficiency_unique_snapshot
ON team_efficiency (
    efficiency_snapshot_id,
    team
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieved_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    status TEXT NOT NULL,
    game_count INTEGER,
    weather_game_count INTEGER,
    indoor_game_count INTEGER,
    source TEXT NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_weather_snapshots_season_week
ON weather_snapshots (
    season,
    week,
    retrieved_at
);

CREATE INDEX IF NOT EXISTS idx_weather_snapshots_status
ON weather_snapshots(status);


CREATE TABLE IF NOT EXISTS nfl_weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weather_snapshot_id INTEGER NOT NULL,

    season INTEGER NOT NULL,
    week INTEGER NOT NULL,

    away_team TEXT NOT NULL,
    home_team TEXT NOT NULL,

    stadium_id TEXT,
    stadium TEXT,
    city TEXT,

    roof_type TEXT NOT NULL,
    weather_relevant INTEGER NOT NULL,

    kickoff_et TEXT,
    local_kickoff TEXT,
    forecast_time TEXT,

    temperature_f REAL,
    precipitation_in REAL,
    weather_code INTEGER,
    wind_mph REAL,
    wind_gust_mph REAL,

    snapshot_path TEXT,

    FOREIGN KEY (weather_snapshot_id)
        REFERENCES weather_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_nfl_weather_snapshot
ON nfl_weather(weather_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_nfl_weather_matchup
ON nfl_weather (
    season,
    week,
    away_team,
    home_team
);

CREATE INDEX IF NOT EXISTS idx_nfl_weather_stadium
ON nfl_weather(stadium_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_nfl_weather_unique_snapshot
ON nfl_weather (
    weather_snapshot_id,
    away_team,
    home_team
);

CREATE TABLE IF NOT EXISTS prediction_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    created_at TEXT NOT NULL,
    sport TEXT NOT NULL,
    season INTEGER,
    week INTEGER,

    collection_run_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    commence_time TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,

    model_version TEXT NOT NULL,
    snapshot_type TEXT NOT NULL DEFAULT 'RESEARCH',

    sportsbook_count INTEGER,

    home_market_probability REAL,
    away_market_probability REAL,

    home_model_probability REAL,
    away_model_probability REAL,

    model_disagreement_team TEXT,
    model_disagreement_pp REAL,
    research_status TEXT,

    home_best_moneyline REAL,
    home_best_moneyline_book TEXT,
    away_best_moneyline REAL,
    away_best_moneyline_book TEXT,

    home_fair_moneyline REAL,
    away_fair_moneyline REAL,

    home_spread REAL,
    away_spread REAL,
    total REAL,

    efficiency_snapshot_id INTEGER,
    efficiency_through_week INTEGER,

    home_off_epa_per_play REAL,
    home_def_epa_per_play REAL,
    home_off_success_rate REAL,
    home_dropback_epa_per_play REAL,
    home_rush_epa_per_play REAL,
    home_recent_games INTEGER,
    home_recent_off_epa_per_play REAL,
    home_recent_def_epa_per_play REAL,
    home_recent_off_success_rate REAL,
    home_recent_dropback_epa_per_play REAL,
    home_recent_rush_epa_per_play REAL,

    away_off_epa_per_play REAL,
    away_def_epa_per_play REAL,
    away_off_success_rate REAL,
    away_dropback_epa_per_play REAL,
    away_rush_epa_per_play REAL,
    away_recent_games INTEGER,
    away_recent_off_epa_per_play REAL,
    away_recent_def_epa_per_play REAL,
    away_recent_off_success_rate REAL,
    away_recent_dropback_epa_per_play REAL,
    away_recent_rush_epa_per_play REAL,

    injury_snapshot_id INTEGER,
    injury_status TEXT,
    injury_expected_week INTEGER,
    injury_latest_week INTEGER,

    weather_snapshot_id INTEGER,
    weather_status TEXT,
    weather_freshness TEXT,
    weather_horizon_hours REAL,
    stadium TEXT,
    roof_type TEXT,
    weather_relevant INTEGER,
    temperature_f REAL,
    precipitation_in REAL,
    wind_mph REAL,
    wind_gust_mph REAL,

    notes TEXT,

    FOREIGN KEY (collection_run_id)
        REFERENCES collection_runs(id),

    FOREIGN KEY (efficiency_snapshot_id)
        REFERENCES efficiency_snapshots(id),

    FOREIGN KEY (injury_snapshot_id)
        REFERENCES injury_snapshots(id),

    FOREIGN KEY (weather_snapshot_id)
        REFERENCES weather_snapshots(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_snapshots_unique
ON prediction_snapshots (
    collection_run_id,
    event_id,
    model_version,
    snapshot_type
);

CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_event
ON prediction_snapshots(event_id);

CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_run
ON prediction_snapshots(collection_run_id);

CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_kickoff
ON prediction_snapshots(commence_time);

CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_status
ON prediction_snapshots(research_status);

CREATE TABLE IF NOT EXISTS prediction_grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    prediction_snapshot_id INTEGER NOT NULL,
    graded_at TEXT NOT NULL,

    game_result_id INTEGER NOT NULL,

    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    winner TEXT NOT NULL,

    model_pick TEXT,
    market_pick TEXT,

    model_correct INTEGER,
    market_correct INTEGER,

    home_model_brier REAL,
    home_market_brier REAL,

    home_model_log_loss REAL,
    home_market_log_loss REAL,

    closing_collection_run_id INTEGER,
    closing_home_market_probability REAL,
    closing_away_market_probability REAL,

    model_clv_pp REAL,
    market_move_toward_model_pp REAL,

    hypothetical_side TEXT,
    hypothetical_price REAL,
    hypothetical_result TEXT,
    hypothetical_profit_units REAL,

    FOREIGN KEY (prediction_snapshot_id)
        REFERENCES prediction_snapshots(id),

    FOREIGN KEY (game_result_id)
        REFERENCES game_results(id),

    FOREIGN KEY (closing_collection_run_id)
        REFERENCES collection_runs(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_grades_snapshot
ON prediction_grades(prediction_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_prediction_grades_result
ON prediction_grades(game_result_id);

CREATE INDEX IF NOT EXISTS idx_prediction_grades_closing_run
ON prediction_grades(closing_collection_run_id);
