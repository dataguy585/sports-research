import sqlite3
from database.db import DB_PATH


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            pg.id AS grade_id,
            pg.prediction_snapshot_id,
            gr.event_id,
            gr.home_team,
            gr.away_team,
            pg.home_score AS graded_home_score,
            pg.away_score AS graded_away_score,
            gr.home_score AS actual_home_score,
            gr.away_score AS actual_away_score
        FROM prediction_grades pg
        JOIN game_results gr
          ON gr.id = pg.game_result_id
        WHERE pg.home_score IS NOT gr.home_score
           OR pg.away_score IS NOT gr.away_score
           OR pg.winner IS NOT gr.winner
    """).fetchall()

    print("\n=== MARKETEDGE GRADE CONSISTENCY ===")
    print(f"Inconsistent grades: {len(rows)}")

    for row in rows:
        print(
            f"Grade {row['grade_id']} | "
            f"{row['away_team']} @ {row['home_team']} | "
            f"Graded: {row['graded_home_score']}-"
            f"{row['graded_away_score']} | "
            f"Current: {row['actual_home_score']}-"
            f"{row['actual_away_score']}"
        )

    conn.close()

    if rows:
        print("STATUS: INCONSISTENT")
        raise SystemExit(1)

    print("STATUS: VALID")


if __name__ == "__main__":
    main()
