import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.prefetch.specific_recall import specific_recall, detect_artifact_type, keywords_from_query, detect_recency_hint
from agent.helpers.time_resolver import resolve_temporal_range

tests = [
    "describe the photo I used for generating the image by AI in last 20 days",
    "what errors did I get in clippy vision in last 20 days",
    "what was the last thing I copied",
    "what was I working on related to the router classifier in last 20 days",
    "what was I seeing on the screen related to graduation in last 20 days",
]

for q in tests:
    tr  = resolve_temporal_range(q)
    art = detect_artifact_type(q)
    kws = keywords_from_query(q)
    rec = detect_recency_hint(q)
    print("=" * 70)
    print(f"Q: {q}")
    print(f"   artifact={art}  recency={rec}  time_scope={tr.phrase if tr else None}")
    print(f"   keywords={kws}")
    print()
    result = specific_recall(q, temporal_range=tr)
    print(result)
    print()
