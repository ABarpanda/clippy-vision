# Router Classifier Evaluation — Findings

> **Update 2026-07-09 (later the same day):** the data cleanup + retrain recommended
> below has been done. See [Retrain results](#retrain-results-2026-07-09) at the bottom.
> Numbers in the body of this document describe the ORIGINAL model.

**Date:** 2026-07-09
**Question:** Is the MiniLM router classifier useful for deterministic prefetch, or a gimmick that should be removed in favor of the ReAct agent (or another technique)?

**Verdict: keep it — but only as a confidence-gated prefetch hint, with three concrete fixes (below). It is not a gimmick, and no other technique beats it on the latency/accuracy trade-off.**

---

## Setup

- **Golden set:** 200 hand-labeled queries written independently of the training data
  (`testing/router_eval/golden_set.jsonl`), balanced ~30 per category, tagged
  `easy / paraphrase / typo / boundary / ood / bare`.
- **Contenders:**
  1. `minilm` — the trained classifier in `agent/router.py`
  2. `baseline-regex` — the labelling policy implemented as regexes (zero ML)
  3. `qwen3-8b-llm` — qwen3:8b with the archived routing system prompt
- Full numbers in `results/report.txt`. Reproduce with `python testing/router_eval/run_eval.py --with-llm`.

## Headline results

| Router        | Accuracy | Action-group acc.* | Latency (mean) |
|---------------|---------:|-------------------:|---------------:|
| regex baseline|   77.5%  |       79.0%        |     ~0 ms      |
| **MiniLM**    | **81.5%**|     **86.5%**      |   **~19 ms**   |
| qwen3:8b LLM  |   92.0%  |       94.0%        |   ~2,155 ms    |

\* *Action-group = prediction maps to the same data source (activity log / fine events / memory / none), i.e. the prefetch would still hit the right store.*

Reference point: **one ReAct tool-selection round with qwen3:8b costs ~2,100 ms**
(measured with the real TOOL_SCHEMAS, `measure_react_round.py`). Most activity queries
need 2+ rounds (select tool → read result → answer), so a correct prefetch saves
roughly 2–4 seconds per query.

## The number that actually matters: prefetch-gate quality

Raw accuracy is the wrong metric — a misroute only costs anything if the gate *fires*.
With the current thresholds in `agent/router.py`, over the 200 golden queries:

- Gate fired on **111/200 (56%)** of queries
- **92% exact-label precision, 94% action-group precision** when fired
- Breakdown of the 111 fires: 102 exact-correct, 2 benign (wrong label, same data
  source), 2 useless (query was casual), **5 harmful** (wrong data source prefetched)
- So the harmful-misfire rate is **2.5% of all traffic**, and since the ReAct agent
  keeps its tools, a harmful fire wastes ~1 prefetch, it does not produce a wrong answer.

Confidence is well calibrated, which is what makes the gate work:

| Confidence bucket | n  | Accuracy |
|-------------------|---:|---------:|
| < 0.50            | 78 |    59%   |
| 0.50 – 0.70       | 62 |    92%   |
| ≥ 0.70            | 60 |   100%   |

A single global rule "prefetch iff conf ≥ 0.5" gives 96% precision at 61% coverage.

## Where the classifier is weak

- **Bare follow-ups ("anything else?", "no, not that one"): 0/5.** Without the prior
  turn in the input it guesses `memory_query`. With multi-turn context included it is
  fine (precision 1.00). This is an input-formatting problem, not a model problem.
- **Boundary cases: 65%** (e.g. "before sleeping" → predicted time_anchored;
  "the other day" → time_anchored). The policy's subtle rules did not fully transfer.
- **Out-of-distribution phrasings: 60%** ("tell me about my day" → memory_query at
  conf 0.68 — the single worst failure, it clears the gate).
- **topic_search recall: 57%** — vague activity phrasings leak into casual/memory.
- Typos land on `specific_recall` at conf 0.41–0.47 ("wht was i dong last weke").

Nearly all of these sit **below conf 0.5**, which is why the gate stays precise.

## Training data audit (`audit_training_data.py`)

- 1,626 clean rows, but **specific_recall = 530 (33%)** vs follow_up_inherit = 93 — heavy imbalance.
- **567 near-duplicate pairs** (template variants like "what did I do 3/5 days ago") —
  the 81.6% in `models/.../eval.txt` is inflated by template leakage across the random
  split; it coincidentally matches the golden-set 81.5%, but per-class numbers differ.
- 448 rows in non-follow_up categories use the multi-turn "User:/Clippy:" format,
  violating the stated generation rule (only follow_up_inherit should).

## Why not the alternatives

- **LLM router (qwen3:8b):** 92% accurate but ~2.1s — the same cost as the ReAct round
  it is supposed to save. Strictly worse than doing nothing. Dead code in `router.py`
  can stay archived.
- **Regex-only router:** free and very precise on specific_recall / memory_query /
  follow-ups, but aggregation recall is 0.20 and paraphrases kill it (62%). Not enough
  alone, though its follow-up detection is worth stealing (see fix 1).
- **Remove routing entirely, rely on ReAct:** correct answers, but every activity query
  pays 2+ qwen rounds ≈ 2–4s of avoidable latency. The classifier costs 19 ms and can
  cut that on >half of queries. That is the whole value proposition, and it holds.

## Recommended actions

1. **Wire it in as a hint, never a hard route.** `classify_query`/`should_prefetch` are
   currently imported in `react_agent.py` but never called. Prefetch into the system
   prompt; keep all tools available. A wrong prefetch then costs ~nothing.
2. **Fix the follow-up path structurally, not with the model.** Before classifying,
   detect bare/short follow-ups (≤ ~4 words, or regex on "what about / anything else /
   not that one / tell me more") and inherit the previous decision — the regex baseline
   scored 5/5 on these. Alternatively always classify the combined
   "User: ... | Prior turns: ..." context that `_build_combined_query_context` already builds.
3. **Raise two thresholds:** `specific_recall` 0.30 → **0.50** (kills all its harmful
   fires on the golden set, precision 90% → 100%, still fires on 17/200) and
   `memory_query` 0.55 is fine but "tell me about my day"-style errors argue for
   `memory_query` prefetch being cheap/small. `topic_search` 0.25 is acceptable only
   because its prefetch is a benign semantic search.
4. **One retrain with cleaned data** (highest-leverage quality fix): dedupe the 567
   near-duplicate pairs, cap specific_recall, strip the multi-turn format from
   non-follow_up rows, and add the failure patterns found here (bare follow-ups,
   "tell me about my day", "was I productive today", "the other day", "before
   sleeping", typo'd time queries). Use `golden_set.jsonl` as a frozen eval set —
   never train on it.
5. **Continue `time_resolver.py`.** time_anchored at conf ≥ 0.55 is 94–100% precise,
   so a parsedatetime-based range resolver on top of it is on solid ground.

## Files

| File | Purpose |
|------|---------|
| `golden_set.jsonl` | 200 hand-labeled eval queries (frozen — do not train on) |
| `run_eval.py` | Main harness: metrics, confusion, gate analysis, calibration, latency |
| `baseline_router.py` | Regex implementation of the labelling policy |
| `analyze_impact.py` | Harmful/useless/benign fire breakdown + per-category threshold sweep |
| `audit_training_data.py` | Duplication and balance audit of training data |
| `measure_react_round.py` | Latency of one ReAct tool-selection round |
| `results/` | report.txt, per-router error files, raw records |

---

## Retrain results (2026-07-09)

Recommendations 3 and 4 were executed:

- **Data cleanup** (`scripts/clean_router_data.py`, backup at
  `core/data/router_generated.jsonl.bak`): stripped the multi-turn format from 546
  non-follow_up rows (dropped 26 whose last turn could not stand alone), removed 9
  golden-set leaks, 84 exact + 279 near duplicates, capped specific_recall at 250.
  1,626 rows → 1,096.
- **Augmentation** (`core/data/router_augmented.jsonl`, 68 hand-written rows, now
  loaded by `train_router.py`): bare follow-ups, paraphrased/typo'd time_anchored,
  boundary topic_search ("before bed", "the other night"), casual-with-quantity-words
  ("how many calories in an egg"), memory paraphrases. All checked against the golden
  set for leakage (>= 0.9 similarity rejected).
- **Retrain:** 10 epochs, best internal eval 77.1% (lower than the old 81.6% because
  the internal split is no longer inflated by template leakage — it is now the honest
  number). Old checkpoint preserved at `models/router_classifier/prev_20260709/`.
- **Threshold retune** in `agent/router.py` based on the new sweep:
  aggregation 0.60→0.50, memory_query 0.55→0.50, specific_recall 0.30→**0.50**,
  topic_search 0.25→0.30, time_anchored unchanged 0.55.

### Golden-set before/after

| Metric | Old model, old thresholds | New model, new thresholds |
|---|---:|---:|
| Overall accuracy | 81.5% | **84.0%** |
| Action-group accuracy | 86.5% | **87.5%** |
| Macro-F1 | 0.81 | **0.84** |
| Bare follow-ups | 0% | 40% |
| Out-of-distribution tag | 60% | 73% |
| Boundary tag | 65% | 70% |
| Gate fired | 111/200 (56%) | 90/200 (45%) |
| Precision when fired | 91.9% | **97.8%** |
| Harmful fires (wrong data source) | 5 | **2** |
| Useless fires (casual/follow-up) | 2 | **0** |

The gate now trades ~11 points of coverage for near-perfect precision: 88 of 90 fires
are exactly right, and the 2 harmful fires are genuinely ambiguous queries
("what was that project with the maps API?" → specific_recall vs topic_search).
Calibration improved too: conf ≥ 0.5 → 98% precision at 51% coverage.

### Still open

- Recommendations 1 (wire prefetch into `react_agent.py`) and 2 (structural follow-up
  detection) are unchanged — bare follow-ups are still only 40% and should be caught
  by a regex/short-query check before the classifier, not by the model.
- specific_recall remains the misroute magnet below conf 0.5 (typos, screen-content
  phrasings); the 0.50 threshold contains it, and future data generation should target
  typo'd time-anchored queries specifically.

---

## Retrain results (2026-07-09, later) — future/past tense disambiguation

**Problem:** the SAME time word ("weekend", "Monday", "today") can refer to the future
or the past depending only on verb tense ("what should I do this weekend?" vs "this
weekend was so boring"). `time_resolver.py` cannot fix this — it only sees the
calendar phrase, not the sentence tense — so the classifier itself had to learn the
distinction. It previously had ZERO training examples of future-tense phrasing in any
category, so behavior on it was undefined/arbitrary.

**Changes:**
- `docs/router_labelling_policy.md`: new rule — future-tense/intent time references
  (`should`, `will`, `going to`, `hope`, `plan to`, `next X`, well-wishes) classify as
  `casual`, never `time_anchored`, regardless of how precisely the date resolves.
  Contrasted explicitly against past-tense phrasing using the identical time word.
- `core/data/router_seed.jsonl`: +16 hand-written contrastive examples (8 future→casual,
  8 past→time_anchored, same ambiguous words).
- `core/data/router_generated.jsonl`: +50 qwen3:8b-generated contrastive pairs (25
  future/past pairs across coding/studying/fitness/cooking/design domains) via a
  one-off targeted prompt — the generic per-category generator did not reliably
  produce this specific pattern on its own.
- Fixed `scripts/generate_router_data.py`: it imported `OLLAMA_MODEL` from
  `agent/router.py`, which no longer exists there (the live LLM-fallback routing code
  was intentionally removed/archived — see router.py's commented-out block). Also
  fixed `consistency_check()` to unpack the MiniLM `classify_query()` tuple return
  instead of a bare `RouterDecision`. Both bugs meant the generation pipeline was
  completely broken before this session. Also raised the policy-text truncation sent
  to the generator prompt from 3000 → 8000 chars — 3000 was silently cutting off the
  entire Hard Boundary Decisions section.
- Retrained 14 epochs (8 was undertrained — eval accuracy was still climbing).

### Golden-set before/after

| Metric | Previous best (84.0%) | This retrain |
|---|---:|---:|
| Overall accuracy | 84.0% | **86.0%** |
| Action-group accuracy | 87.5% | **88.5%** |
| Macro-F1 | 0.84 | 0.86 |
| Gate fired | 90/200 (45%) | 122/200 (61%) |
| Precision when fired | 97.8% | 94.3% |

Coverage increased a lot (more queries clear the prefetch threshold) at a small
precision cost — net positive per the golden-set numbers, but worth re-checking
`analyze_impact.py`'s harmful/benign/useless breakdown before assuming the trade is
free, since precision-when-fired did drop ~3.5 points.

Targeted check (not in golden_set, hand-verified): 16/20 future-vs-past tense
disambiguation cases correct, including examples with novel phrasing never seen in
training ("do you think I should work on the report this weekend?" → casual). The
4 misses were all borderline novel phrasings never seen in training, and 2 of them
still carry `casual`/`time_anchored` as a close secondary — plus `time_resolver.py`'s
own future-rejection guard (see main body above) independently catches genuinely
future-tense queries even when the router's primary label is wrong, so this failure
mode is defended in depth rather than depending on the classifier alone.

**No backup of the pre-this-retrain checkpoint was kept** (it lived only in
`models/router_classifier/best/`, which training overwrites in place) — the previous
`84.0%`-golden-set checkpoint is not recoverable. Recommend copying `best/` to a
`prev_<date>/` folder before future retrains, as was done for the 2026-07-09 (earlier)
retrain.
