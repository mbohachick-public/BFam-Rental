# Payments & booking workflow — handoff bundle

This folder contains the **Codex handoff** product and technical specs (copied from `assets/bohachick-codex-handoff-bundle.zip`).

## Apply database changes

Run in the **Supabase SQL Editor** (after backup), **as two separate runs** (PostgreSQL cannot use new enum labels in the same transaction as `ADD VALUE`; see `55P04`):

1. [`../supabase-migration-booking-workflow-phase1-step1-enum.sql`](../supabase-migration-booking-workflow-phase1-step1-enum.sql) — enum labels only; run and wait for success.
2. [`../supabase-migration-booking-workflow-phase1-step2-schema.sql`](../supabase-migration-booking-workflow-phase1-step2-schema.sql) — `pending` → `requested`, new columns, `booking_events`.

The file [`../supabase-migration-booking-workflow-phase1.sql`](../supabase-migration-booking-workflow-phase1.sql) is a short pointer to these two steps (do not rely on it as a single executable migration).

Until both steps are applied, the API may fail when inserting `requested` or writing new columns.

## Documents

| File | Contents |
|------|----------|
| `01-product-requirements.md` | Business rules, statuses, deposits, phases |
| `02-technical-spec.md` | Entities, state machine, API sketch |
| `03-ux-copy-and-emails.md` | Copy, form labels, email bodies |
| `04-acceptance-checklist.md` | Build order and QA checklist |

Implementation status is tracked in the repo **Implementation plan** (`Specs/Implementation-Plan.md`).
