# BFam Rentals Codex Handoff Bundle

This bundle contains implementation-ready artifacts for adding payments, deposits, booking approval, and contractor check handling to bohachickrentals.com.

## Files
- `01-product-requirements.md` — business requirements, statuses, and rules
- `02-technical-spec.md` — data model, state machine, endpoints, and integration details
- `03-ux-copy-and-emails.md` — on-site copy, form labels, and email templates
- `04-acceptance-checklist.md` — implementation sequence and QA checklist

## Recommended usage with Codex
Prompt Codex with:
1. the technical spec
2. the acceptance checklist
3. the instruction to preserve the existing catalog/request flow
4. the instruction to implement phase 1 first

## Suggested initial Codex prompt
Use the attached specs to implement phase 1 of the booking approval, payments, deposits, and agreement workflow for bohachickrentals.com. Preserve the current catalog and request-first UX. Do not convert the site into full ecommerce checkout. New booking requests must start as requested, not confirmed. Add admin approval, Stripe-backed payment collection, deposit tracking, agreement signing state, and the required guardrails so no trailer can be checked out without payment, deposit, and signed agreement.
