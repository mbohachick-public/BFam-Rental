# Contract + e-sign (Codex bundle)

Source: `assets/bohachick-contract-signing-codex-bundle.zip` (copied here as `01–04` + this README).

## How this maps to the BFam-Rental codebase

| Bundle concept | Implementation |
|------------------|----------------|
| `bookings` | `booking_requests` (existing) |
| `APPROVED_AWAITING_SIGNATURE` | `booking_request_status` = **`approved_awaiting_signature`** |
| After customer signs | `approved_pending_payment` or `approved_pending_check_clearance` (unchanged Phase 1 payment path) + `agreement_signed_at` set by the sign API |
| `SIGNED_AWAITING_PAYMENT` | Same as **`approved_pending_payment`** after signature (payment + deposit still required) |
| `SIGNED_AWAITING_CHECK_CLEARANCE` | Same as **`approved_pending_check_clearance`** after signature |
| `CONFIRMED` | Unchanged: admin **confirm** after marks |
| Document snapshots | `booking_documents` (`RENTAL_AGREEMENT`, `DAMAGE_FEE_SCHEDULE`, `EXECUTED_PACKET`) |
| Signing token | `booking_action_tokens` (SHA-256 of raw token; `SIGN` action) |
| Customer sign page | Frontend `/booking-actions/:token/sign` → API `GET/POST /booking-actions/{token}/sign` |

## Database

`booking_documents`, `booking_signatures`, `booking_action_tokens`, and the **`approved_awaiting_signature`** status are created by **`Specs/supabase-setup.sql`** (PART 1). **PART 0** drops existing BFam tables first (destructive).

## Configuration (backend)

- **`FRONTEND_PUBLIC_URL`** — base URL for signing links in emails (e.g. `https://app.example.com` or `http://127.0.0.1:5173`).
- **`SIGNING_TOKEN_TTL_DAYS`** — optional; default 14.

## API (high level)

- **Public:** `GET/POST /booking-actions/{token}/sign`, `GET /booking-actions/{token}/complete`
- **Admin:** `POST /admin/booking-requests/{id}/resend-signature` (returns JSON with `signing_url` and re-sends email when SMTP is configured)

## Out of scope / later

- DocuSign and multi-signer flows (per product spec MVP).
- **Regenerate signing packet** after admin edits binding terms (manual: decline + re-request or future endpoint).
- Native payment checkout (still manual marks + optional payment link template).
