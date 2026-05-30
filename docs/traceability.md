# Traceability

## What this does
Explains how tailoring outputs can be audited during review.

## What happens internally
Generated resume artifacts include `traceability.json`, which records:
- matched `resume_nodes` ids returned by Qdrant retrieval
- hierarchy context used for tailoring
- rewrite decisions (kept vs rewritten) and the immutable spans that were targeted

