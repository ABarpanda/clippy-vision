"""Topic search: semantic search over session summaries, with optional
time-window scoping from time_resolver.

Handler for the router's 'topic_search' category. Reuses the same
nomic-embed-text + cosine ranking already in retrieval.py, but:
  - No LLM-generated SQL (avoids the date-filter hallucination problem)
  - Searches all 90 days of history when no time anchor is given
  - Applies a lightweight entity-boost as a secondary re-ranking signal
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from pathlib import Path

from core.llm_gateway import gateway, Priority

_DB_PATH = Path(__file__).parent.parent / "core" / "data" / "events.db"
_conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=30)
_conn.execute("PRAGMA journal_mode=WAL")

EMBED_MODEL = "nomic-embed-text"
MAX_RESULTS = 20
MAX_CHARS   = 4000

_STOPWORDS = {
    "what", "have", "been", "doing", "with", "about", "tell", "show",
    "me", "my", "the", "a", "an", "and", "or", "in", "on", "for",
    "of", "to", "i", "was", "is", "are", "did", "do", "any", "all",
    "last", "this", "that", "those", "these", "how", "when", "where",
    "who", "which", "can", "you", "give", "find", "get", "list",
    "stuff", "things", "work", "worked", "working",
}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _extract_keywords(query: str) -> list[str]:
    """Non-stopword tokens > 2 chars. Quoted phrases are kept whole."""
    tokens = re.findall(r'"[^"]+"|\b\w+\b', query.lower())
    return [t.strip('"') for t in tokens
            if t.strip('"') not in _STOPWORDS and len(t.strip('"')) > 2]


def _entity_boost(keywords: list[str], entities_json: str | None) -> float:
    """Small bonus [0, 0.15] when query keywords appear in the entities column.
    Nudges ranking but never overrides semantic score."""
    if not entities_json or not keywords:
        return 0.0
    try:
        ents = [e.lower() for e in json.loads(entities_json)]
    except Exception:
        return 0.0
    hits = sum(1 for kw in keywords if any(kw in e for e in ents))
    return min(hits * 0.05, 0.15)


def _date_filter(temporal_range) -> str:
    """SQL WHERE fragment (no WHERE keyword) scoped to the given range, or all history."""
    base = "summary IS NOT NULL AND summary != ''"
    if temporal_range is None:
        return base
    return (
        f"window_start >= {temporal_range.start_ts} "
        f"AND window_start < {temporal_range.end_ts} "
        f"AND {base}"
    )


def _backfill_embeddings(pairs: list[tuple[str, str]]) -> None:
    texts = [s for _, s in pairs if s]
    if not texts:
        return
    try:
        vecs = gateway.embed(texts, embed_model=EMBED_MODEL, priority=Priority.BACKGROUND)
        for (summary_id, _), vec in zip(pairs, vecs):
            _conn.execute(
                "UPDATE sessions SET summary_embedding = ? WHERE summary_id = ?",
                (json.dumps(vec), summary_id),
            )
        _conn.commit()
    except Exception:
        pass


def topic_search(query: str, temporal_range=None) -> str:
    """Search sessions by topic across all history (or within temporal_range).

    temporal_range: a TemporalRange from time_resolver, or None for all history.
    Returns formatted text ready to pass to the agent as a tool result.
    """
    keywords    = _extract_keywords(query)
    date_filter = _date_filter(temporal_range)

    try:
        q_vec = gateway.embed(query, embed_model=EMBED_MODEL, priority=Priority.INTERACTIVE)
    except Exception as e:
        return f"topic_search: embedding failed — {e}"

    sql = f"""
        SELECT summary_id, window_start, summary, active_task, entities, summary_embedding
        FROM sessions
        WHERE {date_filter}
    """
    try:
        rows = _conn.execute(sql).fetchall()
    except Exception as e:
        return f"topic_search: DB error — {e}"

    if not rows:
        scope = "in the requested time window" if temporal_range else "across all history"
        return f"topic_search: no session summaries found {scope}."

    scored = []
    unembedded = []
    score = 0.0

    for (summary_id, ws, summary, active_task, entities, emb_json) in rows:
        if emb_json:
            score = _cosine(q_vec, json.loads(emb_json))
        else:
            score = 0.0
            unembedded.append((summary_id, summary))
        score += _entity_boost(keywords, entities)
        scored.append((score, ws, summary, active_task, entities))

    if unembedded:
        _backfill_embeddings(unembedded)

    scored.sort(key=lambda x: x[0], reverse=True)
    top    = scored[:MAX_RESULTS]
    total  = len(scored)

    result_parts = []
    for score, ws, summary, active_task, entities in top:
        ts    = time.strftime("%Y-%m-%d %H:%M", time.localtime(ws))
        parts = [f"time: {ts}", f"summary: {summary}", f"score: {score}"]
        if active_task:
            parts.append(f"active_task: {active_task}")
        if entities:
            parts.append(f"entities: {entities}")
        result_parts.append("\n".join(parts))

    shown = len(result_parts)
    if total > shown:
        header = (
            f"topic_search results (showing {shown} most relevant of {total} total — "
            f"call search_events for finer detail):"
        )
    else:
        header = f"topic_search results ({shown} sessions matched):"

    result = header + "\n\n" + "\n---\n".join(result_parts)
    if len(result) > MAX_CHARS:
        result = result[:MAX_CHARS] + f"\n... (truncated to {MAX_CHARS} chars)"
    return result


if __name__ == "__main__":
    from agent.time_resolver import resolve_temporal_range
    while True:
        q = input("Query: ").strip()
        if not q:
            continue
        tr = resolve_temporal_range(q)
        if tr:
            print(f"  time scope: {tr.phrase!r}  [{tr.granularity}]")
        print(topic_search(q, temporal_range=tr))
        print()