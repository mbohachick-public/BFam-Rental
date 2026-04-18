-- =============================================================================
-- Phase 1 — Booking workflow (split across two transactions for PostgreSQL)
-- =============================================================================
-- This file is a POINTER ONLY. Do not paste it into Supabase as one script.
--
-- PostgreSQL error 55P04: new enum values from ALTER TYPE ... ADD VALUE are
-- not usable until that transaction commits. Supabase SQL Editor runs one
-- script = one transaction, so enum adds + UPDATE ... 'requested' must split.
--
-- Run IN ORDER (two separate “Run” actions in the SQL Editor):
--
--   1) supabase-migration-booking-workflow-phase1-step1-enum.sql
--   2) supabase-migration-booking-workflow-phase1-step2-schema.sql
--
-- If step1 already succeeded once, you only need step2 (step1 is idempotent).
-- =============================================================================

SELECT 'Open and run step1, then step2 — see comments in this file.' AS instruction;
