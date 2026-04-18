# Implementation Plan

## Objective

Wire Stripe Checkout into the current Bohachick Rentals booking flow using the existing screens and statuses.

The current UX should remain intact. Stripe should be added as the payment engine after admin approval.

---

## Existing flow observed from current screens

### Customer item page
The item page currently includes:
- trailer summary card
- availability calendar
- request form
- quote block after calculation

The form currently collects:
- start date
- end date
- driver's license upload
- email
- phone
- first name
- last name
- address
- notes
- company / contractor name
- payment preference
- repeat contractor checkbox
- acknowledgment checkbox

The quote block currently shows:
- Days
- Rental subtotal
- Sales tax
- Rental total (with tax)
- Deposit (hold)

### Admin page
Admin sees:
- booking requests grouped/listed by status
- request details
- payment path selector
- Approve / Decline actions
- manual buttons for:
  - Mark rental paid
  - Mark deposit secured
  - Mark agreement signed
  - Confirm booking

---

## Desired Phase 1 flow

### Customer side
No major changes to the request form UX.

Flow remains:
1. User fills request form
2. User gets quote
3. User submits request

### Admin side
After approval:
1. Booking moves to `approved_pending_payment`
2. Admin can click `Generate payment link`
3. App creates a Stripe Checkout Session for the booking
4. App stores the session ID and checkout URL
5. Admin can copy/send the URL to the customer
6. Customer pays through Stripe
7. Stripe webhook updates rental payment status to paid
8. Admin sees payment updated automatically

### Booking confirmation
Once the booking has:
- rental paid = yes
- deposit secured = yes
- agreement signed = yes

then admin can confirm booking.

---

## Scope

### In scope
- Stripe server SDK integration
- Create one Checkout Session per approved booking
- Use booking-specific totals from app data
- Metadata with booking ID
- Success/cancel URLs
- Webhook for payment status sync
- Admin UI button for session generation
- Admin UI display of checkout link and payment state
- Preserve current manual deposit workflow

### Out of scope
- Replace request flow with immediate checkout
- Dynamic inline Stripe Elements on site
- Deposit authorization holds
- Automatic refunds
- Full accounting sync
- Customer account portal
- Email delivery provider changes unless already present in app

---

## Rollout steps

### Step 1: Data model changes
Add Stripe-specific fields to booking records.

### Step 2: Backend Stripe client
Add Stripe SDK config, environment variables, and helper module.

### Step 3: Checkout session creation endpoint
Create an authenticated admin-only endpoint to generate a Checkout Session from a booking.

### Step 4: Admin UI wiring
Add `Generate payment link` button and session state display.

### Step 5: Payment success page
Add or reuse a simple success page for redirect after payment.

### Step 6: Webhook handler
Handle `checkout.session.completed` and update booking state.

### Step 7: Admin status refinement
Show rental paid automatically when webhook succeeds.

### Step 8: QA in Stripe test mode
Run full booking → approval → payment → sync workflow.

---

## UI changes by screen

### Customer item page
Minimal changes:
- none required for Stripe to work in Phase 1
- optional future enhancement: show "Payment will be requested after approval"

### Quote block
No required layout change.
Optional copy additions:
- "Request only — payment is collected after approval"
- "Deposit is secured separately"

### Admin booking requests list
Add:
- `Generate payment link` button on `approved_pending_payment` bookings when no session exists
- `Copy payment link` button when session exists
- display:
  - Stripe checkout URL presence
  - rental payment status
  - Stripe session ID or truncated reference
  - created timestamp if available

### Payment success page
Add:
- success state message
- booking summary
- next steps
- note that booking is not fully confirmed until deposit and agreement are complete

---

## Recommended implementation order

1. Add schema fields
2. Configure Stripe environment
3. Implement session creation service
4. Implement admin endpoint
5. Implement webhook endpoint
6. Add admin buttons/status
7. Add success page
8. Test end-to-end in Stripe sandbox
9. Remove dependence on manual "Mark rental paid" for Stripe-paid bookings

---

## Acceptance target

The feature is complete when:
- an approved booking can generate a unique Stripe Checkout Session
- the admin can send the Stripe-hosted payment URL
- the customer can pay successfully in Stripe test mode
- the app automatically marks rental payment as paid after webhook receipt
- the admin can continue to manage deposit + agreement as separate steps
