from __future__ import annotations

import hashlib
import html
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from reports.nfl_week import get_current_nfl_week


SEASON = 2026
DB_PATH = Path("database/sports.db")
RAW_DIR = Path("data/raw/injuries/nfl_official")

TEAM_MAP = {
    "49ers": "SF",
    "Bears": "CHI",
    "Bengals": "CIN",
    "Bills": "BUF",
    "Broncos": "DEN",
    "Browns": "CLE",
    "Buccaneers": "TB",
    "Cardinals": "ARI",
    "Chargers": "LAC",
    "Chiefs": "KC",
    "Colts": "IND",
    "Commanders": "WAS",
    "Cowboys": "DAL",
    "Dolphins": "MIA",
    "Eagles": "PHI",
    "Falcons": "ATL",
    "Giants": "NYG",
    "Jaguars": "JAX",
    "Jets": "NYJ",
    "Lions": "DET",
    "Packers": "GB",
    "Panthers": "CAR",
    "Patriots": "NE",
    "Raiders": "LV",
    "Rams": "LA",
    "Ravens": "BAL",
    "Saints": "NO",
    "Seahawks": "SEA",
    "Steelers": "PIT",
    "Texans": "HOU",
    "Titans": "TEN",
    "Vikings": "MIN",
}


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return " ".join(value.split()).strip()


def split_name(full_name: str) -> tuple[str | None, str | None]:
    parts = full_name.strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def extract_reported_week(body: str) -> int | None:
    patterns = (
        r"Injuries\s*-\s*WEEK\s*(\d+)",
        r"Week\s*(\d+)\s*of the 2026 Season",
    )

    for pattern in patterns:
        match = re.search(pattern, body, re.I)
        if match:
            return int(match.group(1))

    return None


def parse_tables(body: str) -> list[dict]:
    pattern = re.compile(
        r'<div class="d3-o-section-sub-title"><span>([^<]+)</span></div>'
        r'.*?'
        r'<table[^>]*class="[^"]*d3-o-reports--detailed[^"]*"[^>]*>'
        r'.*?<tbody>(.*?)</tbody>',
        re.I | re.S,
    )

    row_pattern = re.compile(r"<tr>(.*?)</tr>", re.I | re.S)
    cell_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.I | re.S)

    rows = []

    for team_name_raw, tbody in pattern.findall(body):
        team_name = clean_text(team_name_raw)
        team = TEAM_MAP.get(team_name)

        if not team:
            print(f"WARNING: Unmapped team section: {team_name!r}")
            continue

        for row_html in row_pattern.findall(tbody):
            cells = [clean_text(cell) for cell in cell_pattern.findall(row_html)]

            if len(cells) != 5:
                continue

            player, position, injury, practice_status, game_status = cells
            first_name, last_name = split_name(player)

            rows.append(
                {
                    "team": team,
                    "full_name": player or None,
                    "first_name": first_name,
                    "last_name": last_name,
                    "position": position or None,
                    "injury": injury or None,
                    "practice_status": practice_status or None,
                    "game_status": game_status or None,
                }
            )

    return rows


def main() -> None:
    week = get_current_nfl_week(SEASON)

    if week is None:
        raise SystemExit("Unable to determine current NFL week.")

    url = f"https://www.nfl.com/injuries/league/{SEASON}/reg{week}"

    retrieved_at = datetime.now(timezone.utc)
    retrieved_iso = retrieved_at.isoformat()

    print("=== NFL.COM OFFICIAL INJURY COLLECTOR ===")
    print(f"Season:        {SEASON}")
    print(f"Expected week: {week}")
    print(f"URL:           {url}")
    print()

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 MarketEdge-Lab/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body_bytes = response.read()
            http_status = response.status
    except Exception as exc:
        print(f"STATUS:        ERROR")
        print(f"Error:         {exc}")
        raise SystemExit(1)

    body = body_bytes.decode("utf-8", errors="replace")
    payload_sha256 = hashlib.sha256(body_bytes).hexdigest()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")
    raw_path = RAW_DIR / f"injuries_{timestamp}.html"
    raw_path.write_bytes(body_bytes)

    rows = parse_tables(body)
    reported_week = extract_reported_week(body)

    if not rows:
        status = "ERROR"
    elif reported_week is None:
        status = "ERROR"
    elif reported_week < week:
        status = "STALE"
    elif reported_week == week:
        status = "VALID"
    else:
        status = "ERROR"

    latest_week = reported_week

    print(f"HTTP:          {http_status}")
    print(f"STATUS:        {status}")
    print(f"Rows parsed:   {len(rows)}")
    print(f"Expected week: {week}")
    print(f"Reported week: {reported_week}")
    print(f"Latest week:   {latest_week}")
    print(f"Retrieved at:  {retrieved_iso}")
    print(f"SHA256:        {payload_sha256}")
    print(f"Saved snapshot: {raw_path}")
    print()

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO injury_snapshots (
                retrieved_at,
                season,
                expected_week,
                latest_week,
                status,
                row_count,
                source,
                snapshot_path,
                payload_sha256,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retrieved_iso,
                SEASON,
                week,
                latest_week,
                status,
                len(rows),
                "nfl.com",
                str(raw_path),
                payload_sha256,
                None if status == "VALID" else "No injury rows parsed from NFL.com.",
            ),
        )

        snapshot_id = cursor.lastrowid

        if rows:
            cursor.executemany(
                """
                INSERT INTO nfl_injuries (
                    injury_snapshot_id,
                    season,
                    season_type,
                    game_type,
                    team,
                    week,
                    gsis_id,
                    position,
                    full_name,
                    first_name,
                    last_name,
                    report_primary_injury,
                    report_secondary_injury,
                    report_status,
                    practice_primary_injury,
                    practice_secondary_injury,
                    practice_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    (
                        snapshot_id,
                        SEASON,
                        "REG",
                        "REG",
                        row["team"],
                        reported_week if reported_week is not None else week,
                        None,
                        row["position"],
                        row["full_name"],
                        row["first_name"],
                        row["last_name"],
                        row["injury"],
                        None,
                        row["game_status"],
                        row["injury"],
                        None,
                        row["practice_status"],
                    )
                    for row in rows
                ],
            )

        conn.commit()

    finally:
        conn.close()

    print(f"Database snapshot ID: {snapshot_id}")
    print(f"Database rows inserted: {len(rows)}")

    if status == "ERROR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
