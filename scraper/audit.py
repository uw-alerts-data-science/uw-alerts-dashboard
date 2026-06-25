"""UW Alerts database audit report.

Prints a structured report covering record counts, geocoding coverage, date range,
category distribution, update chains, and data quality flags. Exits 0 if all
hard checks pass, 1 if any FAIL-level issue is found.

Usage:
    python -m scraper.audit
"""

import sys

import psycopg2

from scraper.config import load_config
from scraper.logging_config import setup_logging

logger = setup_logging("scraper.audit")

_SEP = "=" * 62
_SEC = "-" * 62


def _q(conn, sql, *params):
    with conn.cursor() as cur:
        cur.execute(sql, params if params else None)
        return cur.fetchall()


def _scalar(conn, sql, *params):
    return _q(conn, sql, *params)[0][0]


def run_audit(config: dict) -> int:
    conn = psycopg2.connect(config["DATABASE_URL"])
    try:
        failures, warnings = _print_report(conn)
    finally:
        conn.close()

    return 1 if failures > 0 else 0


def _print_report(conn) -> tuple:
    failures = 0
    warnings = 0

    print(_SEP)
    print("  UW ALERTS DATABASE AUDIT REPORT")
    print(_SEP)

    # ── 1. Counts ───────────────────────────────────────────────────
    total_incidents = _scalar(conn, "SELECT COUNT(*) FROM incidents")
    total_alerts = _scalar(conn, "SELECT COUNT(*) FROM alerts")
    orig_alerts = _scalar(
        conn, "SELECT COUNT(*) FROM alerts WHERE alert_type = 'original'"
    )
    upd_alerts = _scalar(
        conn, "SELECT COUNT(*) FROM alerts WHERE alert_type = 'update'"
    )
    null_type = _scalar(conn, "SELECT COUNT(*) FROM alerts WHERE alert_type IS NULL")

    print("\n[ COUNTS ]")
    print(f"  Incidents             {total_incidents:>7}")
    print(f"  Alerts (total)        {total_alerts:>7}")
    print(f"    original            {orig_alerts:>7}")
    print(f"    update              {upd_alerts:>7}")
    _row("    null type", null_type, 0, warn=False)
    if null_type > 0:
        warnings += 1

    # ── 2. Date range ───────────────────────────────────────────────
    rows = _q(
        conn, "SELECT MIN(first_reported_at), MAX(first_reported_at) FROM incidents"
    )
    min_dt, max_dt = rows[0]
    print("\n[ DATE RANGE ]")
    print(f"  Oldest incident       {min_dt}")
    print(f"  Newest incident       {max_dt}")

    # ── 3. Geocoding coverage ───────────────────────────────────────
    rows = _q(
        conn,
        """
        SELECT COUNT(*) FILTER (WHERE lat IS NOT NULL AND lng IS NOT NULL),
               COUNT(*)
        FROM incidents
    """,
    )
    geocoded, total = rows[0]
    pct = (100.0 * geocoded / total) if total > 0 else 0.0
    geo_flag = _flag(pct >= 80, pct >= 50)
    if pct < 50:
        failures += 1
    elif pct < 80:
        warnings += 1

    print("\n[ GEOCODING ]")
    print(f"  Geocoded incidents    {geocoded:>7} / {total} ({pct:.1f}%)  {geo_flag}")

    # ── 4. Data quality ─────────────────────────────────────────────
    orphan_incidents = _scalar(
        conn,
        """
        SELECT COUNT(*) FROM incidents i
        WHERE NOT EXISTS (SELECT 1 FROM alerts a WHERE a.incident_id = i.id)
    """,
    )
    null_full_text = _scalar(
        conn, "SELECT COUNT(*) FROM alerts WHERE full_text IS NULL OR full_text = ''"
    )
    null_raw = _scalar(
        conn,
        "SELECT COUNT(*) FROM alerts WHERE raw_scraped_text IS NULL OR raw_scraped_text = ''",
    )
    null_hash = _scalar(conn, "SELECT COUNT(*) FROM alerts WHERE text_hash IS NULL")
    dup_hashes = _scalar(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT text_hash FROM alerts
            WHERE text_hash IS NOT NULL
            GROUP BY text_hash HAVING COUNT(*) > 1
        ) sub
    """,
    )

    print("\n[ DATA QUALITY ]")
    _row("  Orphan incidents", orphan_incidents, 0, warn=False)
    _row("  Alerts null full_text", null_full_text, 0, warn=False)
    _row("  Alerts null raw_text", null_raw, 0, warn=True)
    _row("  Alerts null hash", null_hash, 0, warn=False)
    _row("  Duplicate hashes", dup_hashes, 0, warn=False)

    if orphan_incidents > 0:
        failures += 1
    if null_full_text > 0:
        failures += 1
    if null_hash > 0:
        failures += 1
    if dup_hashes > 0:
        failures += 1
    if null_raw > 0:
        warnings += 1

    # ── 5. Missing incident fields ──────────────────────────────────
    rows = _q(
        conn,
        """
        SELECT COUNT(*) FILTER (WHERE category IS NULL),
               COUNT(*) FILTER (WHERE nearest_address IS NULL),
               COUNT(*) FILTER (WHERE first_reported_at IS NULL)
        FROM incidents
    """,
    )
    null_cat, null_addr, null_date = rows[0]

    print("\n[ MISSING INCIDENT FIELDS ]")
    _row("  null category", null_cat, 0, warn=True)
    _row("  null nearest_address", null_addr, 0, warn=True)
    _row("  null first_reported_at", null_date, 0, warn=True)
    if null_cat > 0:
        warnings += 1
    if null_addr > 0:
        warnings += 1
    if null_date > 0:
        warnings += 1

    # ── 6. Category distribution ────────────────────────────────────
    cat_rows = _q(
        conn,
        """
        SELECT COALESCE(category, '(null)'), COUNT(*)
        FROM incidents
        GROUP BY category
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """,
    )
    if cat_rows and total_incidents > 0:
        max_count = cat_rows[0][1]
        bar_scale = max(1, max_count // 30)
        print("\n[ CATEGORY DISTRIBUTION ]")
        for cat, count in cat_rows:
            bar = "█" * (count // bar_scale)
            print(f"  {cat:<32} {count:>5}  {bar}")

    # ── 7. Alert chains per incident ────────────────────────────────
    chain_rows = _q(
        conn,
        """
        SELECT alert_count, COUNT(*) AS incident_count
        FROM (
            SELECT incident_id, COUNT(*) AS alert_count
            FROM alerts
            GROUP BY incident_id
        ) sub
        GROUP BY alert_count
        ORDER BY alert_count
    """,
    )
    print("\n[ ALERT CHAINS PER INCIDENT ]")
    for alert_count, incident_count in chain_rows:
        suffix = "alerts" if alert_count != 1 else "alert "
        print(f"  {alert_count} {suffix}  →  {incident_count} incident(s)")

    # ── 8. Source URL coverage ──────────────────────────────────────
    rows = _q(
        conn,
        """
        SELECT COUNT(*) FILTER (WHERE source_url IS NOT NULL AND source_url != 'https://emergency.uw.edu/'),
               COUNT(*) FILTER (WHERE source_url = 'https://emergency.uw.edu/' OR source_url IS NULL),
               COUNT(*)
        FROM alerts
    """,
    )
    permalink_count, generic_count, total_al = rows[0]
    print("\n[ SOURCE URL COVERAGE ]")
    print(f"  Permalink URLs        {permalink_count:>7} / {total_al}")
    print(f"  Generic homepage URL  {generic_count:>7} / {total_al}")

    # ── Verdict ─────────────────────────────────────────────────────
    print(f"\n{_SEP}")
    if failures == 0 and warnings == 0:
        print("  VERDICT: PASS — no issues found")
    elif failures == 0:
        print(f"  VERDICT: PASS WITH WARNINGS — {warnings} warning(s), 0 failures")
    else:
        print(f"  VERDICT: FAIL — {failures} failure(s), {warnings} warning(s)")
    print(_SEP)

    return failures, warnings


def _flag(good: bool, ok: bool = True) -> str:
    if good:
        return "PASS"
    if ok:
        return "WARN"
    return "FAIL"


def _row(label: str, value: int, expected: int, warn: bool) -> None:
    """Print one audit row with a status tag."""
    if value == expected:
        tag = "PASS"
    elif warn:
        tag = "WARN"
    else:
        tag = "FAIL"
    print(f"  {label:<28} {value:>7}  [{tag}]")


if __name__ == "__main__":
    sys.exit(run_audit(load_config()))
