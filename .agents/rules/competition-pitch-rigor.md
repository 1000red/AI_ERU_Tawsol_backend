# Competition Pitch & Educational Presentation Rigor

These rules apply when developing presentations, slide decks, pitch videos, and defense documentation for academic, institutional, or educational competitions (e.g., HP IDEA, Ministry of Communications, WE School challenges).

## 1. No Unsubstantiated Absolute Claims
* **Forbidden Phrases**: "100% dignity", "zero hallucination", "eliminates bullying permanently", "flawless security".
* **Approved Alternatives**:
  - Instead of "100% dignity", specify the mechanism: *"Human-in-the-loop disciplinary triage: positive praise is displayed publicly while behavioral interventions remain strictly private."*
  - Instead of "zero hallucination", state: *"Deterministic exact-quote verification: citations are matched against verified reference documents with human teacher sign-off."*

## 2. Metric Integrity & Honest Units
* **Never inflate relative percentages**: Avoid writing `+160%` or `+57%` without context.
* **State absolute sample numbers**: Write `+8 students participating (from 5 to 13 students in a 14-student cohort)`.
* **Disclose Pilot Limitations**: Always acknowledge trial parameters:
  - *"Two-week pilot in a single cohort (14 students) — treated as Proof-of-Concept."*
  - Explicitly acknowledge the **Hawthorne effect** (novelty effect) and outline the longitudinal phase (e.g. 8-week cross-sectional trial with control group).

## 3. Human-in-the-Loop & Safety Architecture
* In any educational pitch, highlight that AI is an assistant, never the final authority:
  1. **Teacher Approval Gate**: AI generates drafts; human educator must click "Approve" before any record is stored or displayed.
  2. **Instant Kill-Switch**: The administrator has a single-click kill-switch to disable all AI evaluations instantly if anomalous output is observed.
  3. **Data Sovereignty**: Clarify that school student metrics reside in institutional databases (PostgreSQL) and are never ingested for public LLM training.
