import json
import threading
import time

from core.screenshot_enrichment import enrich_screenshot
from core.storage import conn
from core.vision import get_screenshots_near

from .tier_one_classifier import tier1_score
from .tier_two_classifier import classify_with_llm
from .tier_zero_classifier import tier_zero_classifier

POLL_SECS = 2
VISION_POLL_SECS = 5
MAX_VISION_WAIT_SECS   = 300  # skip vision enrichment if event has been waiting longer than this

DEFAULT_SCREENSHOT_VERDICT = {
    "verdict": "not_interesting",
    "score": 5,
    "reason": "No screenshots found near event time",
    "ocr_text": "",
    "user_activity": "",
    "suggested_action": None,
}

OCR_ONLY_VERDICT = {
    "verdict": "not_interesting",
    "score": 5,
    "reason": "Local accessibility and OCR text capture completed",
    "ocr_text": "",
    "user_activity": "",
    "suggested_action": None,
}


# Column migrations live in core.storage._ensure_column. Do not ALTER here:
# a second ADD COLUMN on some Windows SQLite builds raises SystemError and
# kills API startup.

#-----------------------------------------------------#
#------------------- Print functions -----------------#
#-----------------------------------------------------#
def _print_verdict(tier: int, event: dict, verdict: dict):
    verdict_str  = verdict["verdict"].upper()
    score        = verdict["score"]
    reason       = verdict["reason"]
    event_type   = event["event_type"]
    process_name = event["process_name"] or "unknown"
    print(f"  [TIER-{tier}] {verdict_str} (score={score}/10) | {event_type} in {process_name} | {reason}")

def _print_capture_text_verdict(event: dict, verdict: dict):
    verdict_str = verdict["verdict"].upper()
    process_name = event["process_name"] or "unknown"
    print(
        f"  [SCREEN TEXT] {verdict_str} (score={verdict['score']}/10) | "
        f"{event['event_type']} in {process_name} | {verdict['reason']}"
    )
    if verdict.get("user_activity"):
        print(f"    activity : {verdict['user_activity']}")
    if verdict.get("ocr_text"):
        ocr = verdict["ocr_text"].replace("\n", " ")
        preview = ocr[:120] + ("..." if len(ocr) > 120 else "")
        print(f"    ocr      : {preview}")
    if verdict.get("suggested_action"):
        print(f"    next     : {verdict['suggested_action']}")



def apply_verdict(event_id: str, verdict: dict):
    status      = "done"
    interesting = 0 if verdict["verdict"] == "not_interesting" else 1
    cursor = conn.execute(
        """UPDATE events
           SET interesting=?, interest_score=?, interest_reason=?, classification_status=?
           WHERE event_id=?""",
        (interesting, verdict["score"], verdict["reason"], status, event_id)
    )
    conn.commit()
    return bool(cursor.rowcount)

def apply_vision_verdict(
    event_id: str,
    verdict: dict,
    image_embedding: list[float] | None = None,
    image_embedding_model: str | None = None,
    screenshot_filename: str | None = None,
):

    # Vision verdict is authoritative — it can see the screen, so it overrides text-tier classification
    interesting = 0 if verdict["verdict"] == "not_interesting" else 1
    cursor = conn.execute(
        """UPDATE events
           SET vision_ocr_text=?,
               vision_activity=?,
               vision_suggested_action=?,
               vector_embedding=NULL,
               image_embedding=?,
               image_embedding_model=?,
               screenshot_filename=?,
               interesting=CASE WHEN classification_status='done' THEN interesting ELSE ? END,
               interest_score=CASE WHEN classification_status='done' THEN interest_score ELSE ? END,
               interest_reason=CASE WHEN classification_status='done' THEN interest_reason ELSE ? END,
               classification_status='done'
           WHERE event_id=?
             AND classification_status IN ('done', 'awaiting_vision', 'screenshot_only')
             AND vision_ocr_text IS NULL
             AND vision_activity IS NULL
             AND vision_suggested_action IS NULL""",
        (
            verdict.get("ocr_text"),
            verdict.get("user_activity"),
            verdict.get("suggested_action"),
            json.dumps(image_embedding) if image_embedding else None,
            image_embedding_model,
            screenshot_filename,
            interesting,
            verdict.get("score"),
            verdict.get("reason"),
            event_id,
        ),
    )
    conn.commit()
    return bool(cursor.rowcount)


def build_capture_text_verdict(event: dict, captured_text: str) -> dict:
    window = event.get("window_context") or {}
    context = " — ".join(
        value for value in (
            str(window.get("process_name") or "").strip(),
            str(window.get("current_window_title") or "").strip(),
        ) if value
    )
    verdict = dict(OCR_ONLY_VERDICT)
    verdict["ocr_text"] = captured_text
    verdict["user_activity"] = context or str(event.get("summary") or "").strip()
    if not captured_text:
        verdict["reason"] = "No accessibility or OCR text was available"
    return verdict


def _row_to_event(row) -> dict:
    (event_id, timestamp, event_type,
     process_name, current_window_title, active_url,
     prev_process, prev_title,
     summary, payload) = row

    return {
        "event_id":     event_id,
        "timestamp":    timestamp,
        "event_type":   event_type,
        "process_name": process_name,
        "summary":      summary,
        "payload":      payload,
        "window_context": {
            "process_name":         process_name,
            "current_window_title": current_window_title,
            "active_url":           active_url,
        },
        "previous_window_context": {
            "process_name":         prev_process,
            "current_window_title": prev_title,
        } if prev_process else None,
    }


def classify_event(event: dict):

    # Tier 0 — rules (instant, no I/O)
    verdict = tier_zero_classifier(event)
    if verdict:
        _print_verdict(0, event, verdict)
        apply_verdict(event["event_id"], verdict)
        return


    # Tier 1 — feature scoring + personal baseline (cheap)
    verdict = tier1_score(event, conn)
    if verdict:
        _print_verdict(1, event, verdict)
        apply_verdict(event["event_id"], verdict)
        return


    # Tier 2 — LLM with last-3-event context window
    recent = conn.execute(
        """SELECT * FROM (
               SELECT event_type, process_name, summary, timestamp FROM events
               WHERE timestamp < (SELECT timestamp FROM events WHERE event_id = ?)
               AND classification_status = 'done'
               ORDER BY timestamp DESC LIMIT 3
           ) ORDER BY timestamp ASC""",
        (event["event_id"],)
    ).fetchall()

    if recent:
        context_str = "\n".join(f"  [{r[0]}] {r[1]}: {r[2]}" for r in recent)
        summary = f"Recent context:\n{context_str}\n\nCurrent event:\n  {event['summary']}"
    else:
        summary = event["summary"]

    try:
        verdict = classify_with_llm(summary, event["event_type"], event["window_context"])
    except Exception as e:
        print(f"  [TIER-2] Failed: {e} — backing off 30s before retry")
        time.sleep(30)
        return  # leave as 'pending', retry next cycle

    _print_verdict(2, event, verdict)
    apply_verdict(event["event_id"], verdict)

def classify_capture_text_event(event: dict):
    screenshots = get_screenshots_near(event["timestamp"], max_count=1)
    if not screenshots:
        _print_capture_text_verdict(event, DEFAULT_SCREENSHOT_VERDICT)
        apply_vision_verdict(event["event_id"], DEFAULT_SCREENSHOT_VERDICT)
        return


    # Show timing context before sending to the model
    event_ts   = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
    shot_ts_ms = int(screenshots[0].stem.split("_", 1)[0])
    shot_ts    = time.strftime("%H:%M:%S", time.localtime(shot_ts_ms / 1000))
    shot_delta = int(event["timestamp"] - shot_ts_ms / 1000)
    vision_lag = int(time.time() - event["timestamp"])
    print(
        f"  [SCREEN TEXT] event@{event_ts} | screenshot@{shot_ts} "
        f"(Δ{shot_delta:+d}s vs event) | processing lag {vision_lag}s"
    )

    try:
        ocr_text, image_embedding, image_embedding_model = enrich_screenshot(screenshots[0])
    except Exception as e:
        print(f"  [SCREEN TEXT] Screenshot enrichment failed: {e}")
        ocr_text, image_embedding, image_embedding_model = "", None, None

    verdict = build_capture_text_verdict(event, ocr_text)
    _print_capture_text_verdict(event, verdict)
    apply_vision_verdict(event["event_id"], verdict, image_embedding, image_embedding_model, screenshots[0].name)


def worker_loop():
    print("[worker] Classification worker started")
    while True:
        rows = conn.execute(
            """SELECT event_id, timestamp, event_type,
                      process_name, current_window_title, active_url,
                      previous_process_name, previous_window_title,
                      summary, payload
               FROM events
               WHERE classification_status = 'pending'
               ORDER BY timestamp ASC
               LIMIT 10"""
        ).fetchall()

        if not rows:
            time.sleep(POLL_SECS)
            continue

        for row in rows:
            classify_event(_row_to_event(row))

def capture_text_worker_loop():
    print("[worker] Screen text worker started")
    while True:
        rows = conn.execute(
            """SELECT event_id, timestamp, event_type,
                      process_name, current_window_title, active_url,
                      previous_process_name, previous_window_title,
                      summary, payload
               FROM events
               WHERE classification_status IN ('awaiting_vision', 'screenshot_only')
               ORDER BY timestamp DESC
               LIMIT 5"""
        ).fetchall()
        if not rows:
            time.sleep(VISION_POLL_SECS)
            continue
        for row in rows:
            event = _row_to_event(row)
            age_secs = time.time() - event["timestamp"]
            if age_secs > MAX_VISION_WAIT_SECS:

                # Event is too stale for vision enrichment to be useful — mark done and move on
                conn.execute(
                    "UPDATE events SET classification_status='done' WHERE event_id=?",
                    (event["event_id"],)
                )
                conn.commit()
                event_ts = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
                print(f"  [SCREEN TEXT] Skipped stale event@{event_ts} ({age_secs:.0f}s old > {MAX_VISION_WAIT_SECS}s limit)")
                continue
            classify_capture_text_event(event)

def start_capture_text_worker():
    t = threading.Thread(target=capture_text_worker_loop, daemon=True)
    t.start()
    return t

def start_worker():
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    start_capture_text_worker()
    return t
