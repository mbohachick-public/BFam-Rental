# Test Plan

## Overview
This test plan verifies that Stripe Checkout can be added to the existing booking flow without breaking the current request/approval/admin process.

---

## Test data assumptions
Use Stripe sandbox/test mode.
Use at least one real booking fixture based on the current item flow:
- item: 7K Dump Trailer (12')
- booking with 2-day rental
- booking with 3-day rental
- quote values present
- deposit shown but handled separately

---

## Section 1: Quote and booking flow regression

### T1.1 Quote still renders after date selection
**Given** a customer selects valid start and end dates  
**When** they click `Get quote`  
**Then** the quote block shows:
- Days
- Rental subtotal
- Sales tax
- Rental total with tax
- Deposit

### T1.2 Submit request still creates booking request
**Given** a customer completes required request fields  
**When** they click `Submit request`  
**Then** a booking request is created with status `requested`

### T1.3 Existing admin request list still loads
**Given** an admin opens booking requests  
**Then** requested bookings render with current details and actions

---

## Section 2: Approval and Stripe session generation

### T2.1 Approve request moves to approved pending payment
**Given** a booking request in `requested`  
**When** admin clicks `Approve`  
**Then** the booking moves to `approved_pending_payment`

### T2.2 Generate payment link button appears only for approved pending payment
**Given** a booking in `approved_pending_payment`  
**Then** admin sees `Generate payment link`

**And given** a booking in `requested`  
**Then** admin does not see `Generate payment link`

### T2.3 Generate payment link creates Stripe session
**Given** a valid approved booking  
**When** admin clicks `Generate payment link`  
**Then** backend creates a Stripe Checkout Session  
**And** saves:
- session ID
- checkout URL
- created timestamp if implemented

### T2.4 Generated session amount matches booking total
**Given** a booking with rental total including tax  
**When** session is created  
**Then** the Stripe checkout amount equals the booking’s rental total  
**And** does not include deposit in Phase 1

### T2.5 Booking-specific amount supports 3-day rental
**Given** a 3-day booking  
**When** session is created  
**Then** checkout amount matches the 3-day computed quote  
**And** is not based on a static product link amount

---

## Section 3: Stripe checkout behavior

### T3.1 Customer can open checkout URL
**Given** a generated checkout URL  
**When** customer navigates to it  
**Then** Stripe Checkout loads successfully

### T3.2 Successful test card payment completes
Use Stripe test card:
- `4242 4242 4242 4242`

**Given** the customer completes payment  
**Then** Stripe redirects to the success URL  
**And** the app does not require client-side trust to mark paid

### T3.3 Cancel returns safely
**Given** the customer opens checkout  
**When** they cancel  
**Then** they return to cancel URL  
**And** booking remains unpaid

---

## Section 4: Webhook sync

### T4.1 checkout.session.completed marks rental paid
**Given** Stripe sends `checkout.session.completed`  
**When** webhook is verified and processed  
**Then** booking `rental_payment_status` becomes `paid`

### T4.2 Payment timestamp is stored
**Given** a successful webhook  
**Then** booking stores `rental_paid_at`

### T4.3 Payment intent ID stored if available
**Given** session includes a payment intent  
**Then** the app stores `stripe_payment_intent_id`

### T4.4 Duplicate webhook delivery is harmless
**Given** Stripe sends the same event more than once  
**When** webhook handler processes duplicates  
**Then** booking remains correct  
**And** duplicate processing does not create inconsistent state

### T4.5 Missing booking metadata is handled safely
**Given** a malformed webhook with missing `booking_id` metadata  
**Then** the webhook handler logs the issue  
**And** does not crash  
**And** does not mark random bookings paid

---

## Section 5: Admin UI sync

### T5.1 Admin sees rental paid automatically after webhook
**Given** payment succeeded  
**When** admin reloads booking requests  
**Then** booking shows `Rental paid: yes`

### T5.2 Deposit and agreement remain separate
**Given** rental payment is paid  
**Then** admin still must separately set:
- deposit secured
- agreement signed

### T5.3 Confirm booking remains gated
**Given** rental paid = yes but deposit secured = no or agreement signed = no  
**Then** booking cannot be treated as fully confirmed by process rules

---

## Section 6: Security and validation

### T6.1 Non-admin cannot create checkout session
**Given** an unauthenticated or non-admin actor  
**When** calling the session creation endpoint  
**Then** request is denied

### T6.2 Client cannot override amount
**Given** a crafted client request with manipulated totals  
**When** backend creates session  
**Then** backend uses stored booking totals only

### T6.3 Webhook signature verification enforced
**Given** a request to webhook endpoint without valid Stripe signature  
**Then** endpoint rejects it

---

## Section 7: Recovery and edge cases

### T7.1 Admin can still manually reconcile if needed
**Given** webhook delivery fails  
**Then** admin can inspect Stripe session reference and manually reconcile booking payment state

### T7.2 Session regeneration rules behave safely
**Given** a booking has an existing unpaid session  
**When** admin regenerates session if feature is supported  
**Then** new session URL is stored  
**And** paid bookings cannot be accidentally reset

### T7.3 Booking remains stable if checkout created twice accidentally
**Given** admin double-clicks generate  
**Then** app handles race safely  
**And** only one current checkout URL is treated as active

---

## Section 8: Regression notes for current screens

Verify the following existing UI remains stable:
- trailer detail layout
- availability calendar
- quote block formatting
- request form fields
- admin booking request cards
- existing decline and agreement controls
- existing deposit workflow

---

## Exit criteria
Implementation passes when:
- request flow still works
- admin approval still works
- Stripe Checkout Session is generated per approved booking
- payment succeeds in Stripe sandbox
- webhook marks rental paid automatically
- admin can continue deposit/agreement flow without regressions
