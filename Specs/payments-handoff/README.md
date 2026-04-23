# Payments & booking workflow — handoff bundle

This folder contains the **Codex handoff** product and technical specs (copied from `assets/bohachick-codex-handoff-bundle.zip`).

## Apply database changes

Run **[`../supabase-setup.sql`](../supabase-setup.sql)** in the Supabase SQL Editor. **PART 0** drops all BFam application tables and types; **PART 1** creates the full schema (including `booking_request_status` values, workflow columns, and `booking_events`). Until that script has been applied, the API may fail when inserting `requested` or writing new columns.

## Documents

| File | Contents |
|------|----------|
| `01-product-requirements.md` | Business rules, statuses, deposits, phases |
| `02-technical-spec.md` | Entities, state machine, API sketch |
| `03-ux-copy-and-emails.md` | Copy, form labels, email bodies |
| `04-acceptance-checklist.md` | Build order and QA checklist |

Implementation status is tracked in the repo **Implementation plan** (`Specs/Implementation-Plan.md`).
