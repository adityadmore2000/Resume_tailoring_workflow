# Experience Banks (Postgres-backed)

## What a bank is (source of truth)
A bank is a Postgres-backed resume:
- `resumes`: one row per bank/resume (includes a stable `slug`)
- `resume_nodes`: the parsed resume as a tree (sections → items → details)

Qdrant stores embeddings for a subset of `resume_nodes` (nodes marked `metadata.searchable=true`) to support semantic retrieval, scoped by `resume_id`.

## What a bank is not
- Not a folder under `data/experience_bank/`
- Not tracked by `banks_registry.json`
- Not dependent on any `experience_bank_index.json`

Those legacy file-based formats are not part of the supported runtime.

