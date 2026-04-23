-- Add calendar hold for in-flight booking requests (blocks dates until confirm or decline).
-- Run once in Supabase SQL editor on existing databases.

ALTER TYPE public.day_status ADD VALUE IF NOT EXISTS 'pending_request';
