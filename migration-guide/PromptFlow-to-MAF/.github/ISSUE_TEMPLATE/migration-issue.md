---
name: Migration issue
about: Report a problem encountered while migrating from Prompt Flow to MAF
labels: bug
---

## MAF version

    pip show agent-framework | grep Version

Paste output here.

## Prompt Flow node types involved

List the node types from your `flow.dag.yaml` that are relevant to the issue
(e.g. `llm`, `python`, `prompt`, `embed_text`, `vector_db_lookup`).

## Phase

Which phase were you on when the issue occurred?

- [ ] Phase 1 — Audit & Map
- [ ] Phase 2 — Rebuild in MAF
- [ ] Phase 3 — Validate Parity
- [ ] Phase 4 — Migrate Ops
- [ ] Phase 5 — Cut Over

## Sample file

Which sample file (if any) does this relate to?

## What happened

Describe what you expected and what actually occurred.

## Full error output

Paste the complete traceback or error message here.

## Environment

- OS:
- Python version:
- Azure region:
