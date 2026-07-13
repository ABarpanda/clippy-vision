"""
Tier 0 --> Raw events (< 2 hours)
Tier 1 --> Sessions/summaries (< 7 days)
Tier 2 --> Distiller (beyond 7 days)
"""

import sqlite3
import time
import json
from pathlib import Path

from agent.time_resolver import resolve_temporal_range, TemporalRange

DB_PATH = Path(__file__).parent.parent / "core" / "data" / "events.db"
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30.0)
conn.execute("PRAGMA journal_mode = WAL")

EVENT_TIER_MAX_SECONDS = 2 * 60 * 60  # 2 hours'
RAW_EVENTS_TTL_DAYS = 7
SESSION_EVENTS_TTL_DAYS = 90
SESSION_TIER_MAX_SECONDS = 7 * 24 * 60 * 60  # 7 days
MAX_EVENTS = 30

NOISE_TYPES = "('typing_burst', 'deviation', 'context_change')"

###########################################
############# TIER SELECTOR ###############
###########################################


def select_tier(temporal_range: TemporalRange) -> str:
    now = time.time()
    if temporal_range.start_ts > now:
        return "none"
    raw_ttl_cutoff     = now - RAW_EVENTS_TTL_DAYS * 86400
    session_ttl_cutoff = now - SESSION_EVENTS_TTL_DAYS * 86400
    window_seconds     = temporal_range.end_ts - temporal_range.start_ts
    if (
        temporal_range.granularity == "hour"
        and window_seconds <= EVENT_TIER_MAX_SECONDS
        and temporal_range.start_ts >= raw_ttl_cutoff
    ):
        return "events"
    if temporal_range.start_ts >= session_ttl_cutoff:
        return "sessions"
    return "distiller"


def fetch_events(temporal_range: TemporalRange) -> list[dict]:
    now = time.time()
    raw_ttl_cutoff = now - RAW_EVENTS_TTL_DAYS * 24 * 60 * 60

    if temporal_range.end_ts < raw_ttl_cutoff:
        return []
    
    start_ts = max(temporal_range.start_ts, raw_ttl_cutoff)
    sql = f"""
        SELECT
            timestamp, event_type, process_name,
            current_window_title, active_url,
            summary, vision_activity, vision_ocr_text
        FROM events
        WHERE interesting = 1
          AND timestamp >= ?
          AND timestamp < ?
          AND (
              event_type NOT IN {NOISE_TYPES}
              OR vision_ocr_text IS NOT NULL
          )
        ORDER BY timestamp DESC
        LIMIT {MAX_EVENTS}
    """

    try:
        rows = conn.execute(sql, (start_ts, temporal_range.end_ts)).fetchall()
    except Exception:
        return []
    return [
        {
            "timestamp":      r[0],
            "event_type":     r[1],
            "process_name":   r[2],
            "window_title":   r[3],
            "active_url":     r[4],
            "summary":        r[5],
            "vision_activity": r[6],
            "vision_ocr_text": r[7],
        }
        for r in rows
    ]


def format_events(events: list[dict], temporal_range: TemporalRange) -> str:
    if not events:
        start_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(temporal_range.start_ts))
        end_str   = time.strftime("%H:%M",           time.localtime(temporal_range.end_ts))
        return f"[events] no activity recorded between {start_str} and {end_str}."

    date_str = time.strftime("%Y-%m-%d", time.localtime(temporal_range.start_ts))
    parts = [f"[raw events — {date_str}, {len(events)} entries]"]

    for e in events:
        ts_str = time.strftime("%H:%M:%S", time.localtime(e["timestamp"]))
        block = [f"time: {ts_str}"]
        if e["process_name"]:
            block.append(f"app: {e['process_name']}")
        if e["window_title"]:
            block.append(f"window: {e['window_title']}")
        if e["active_url"]:
            block.append(f"url: {e['active_url']}")
        if e["vision_activity"]:
            block.append(f"activity: {e['vision_activity']}")
        if e["summary"]:
            block.append(f"summary: {e['summary']}")
        if e["vision_ocr_text"]:
            ocr = e["vision_ocr_text"]
            display = ocr if len(ocr) <= 300 else ocr[:300] + f"… [{len(ocr)} chars]"
            block.append(f"ocr: {display}")
        parts.append("\n".join(block))

    return "\n\n---\n".join(parts)


def time_anchor_fetch(temporal_range: TemporalRange) -> str:
    tier = select_tier(temporal_range)

    if tier == "none":
        return "No data available for this temporal range (future temporal range)"

    if tier == "events":
        events = fetch_events(temporal_range)
        return format_events(events, temporal_range)

    if tier == "sessions":
        return "Sessions/summaries are not yet supported"

    if tier == "distiller":
        return "Distiller is not yet supported"

    return "Unknown tier"

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.time_resolver import resolve_temporal_range

    while True:
        query = input("Query: ").strip()
        if not query:
            break
        temporal_range = resolve_temporal_range(query)
        if temporal_range is None:
            print("  -> could not resolve a time range from that query")
            continue
        print(f"  -> tier: {select_tier(temporal_range)}")
        print(f"     range: {temporal_range.phrase!r} [{temporal_range.granularity}]")
        print()
        print(time_anchor_fetch(temporal_range))
        print()
    