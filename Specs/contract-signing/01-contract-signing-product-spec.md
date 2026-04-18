# BFam Rentals Contract + E-Sign Integration Product Spec

## Objective
Add the rental contract, damage fee schedule acknowledgment, and signature flow into the existing reservation-first booking workflow on bohachickrentals.com without converting the site into a full ecommerce checkout.

This should preserve the current user journey:
1. Catalog
2. Trailer detail page
3. Booking request submission
4. Manual approval by admin
5. Customer completes contract signing + payment/deposit
6. Booking becomes confirmed

## Core Principles
- A booking request is **not** a confirmed reservation.
- No trailer is released until all three are complete:
  1. rental agreement signed
  2. damage fee schedule acknowledged
  3. payment and deposit secured
- The contract flow should work for both homeowners and contractors.
- Contractors may pay by ACH or approved business check, but must still complete signing.
- The website should clearly show booking status at every stage.

## User Types
### 1. Standard renter
- Usually card payer
- Must sign agreement per booking
- Must authorize deposit per booking

### 2. Contractor renter
- May request ACH or business check
- Must sign agreement per booking unless later upgraded to a stored master agreement flow
- Must have card on file for damage/deposit unless explicitly overridden by admin

## Booking Status Model
Use the following statuses consistently in UI, database, emails, and admin:
- `REQUEST_SUBMITTED`
- `PENDING_REVIEW`
- `APPROVED_AWAITING_SIGNATURE`
- `SIGNED_AWAITING_PAYMENT`
- `SIGNED_AWAITING_CHECK_CLEARANCE`
- `PAYMENT_RECEIVED_AWAITING_DEPOSIT`
- `CONFIRMED`
- `ACTIVE`
- `RETURNED_PENDING_INSPECTION`
- `COMPLETED`
- `CANCELLED`

## Required Documents
### A. Rental Agreement
This is the main trailer rental contract.

### B. Damage Fee Schedule Addendum
This must be included in the signing experience and acknowledged by the renter.

## Recommended Signing UX
### Where signing happens
Signing should happen **after admin approval**, not during the initial booking request.

### Why
- avoids collecting signatures for requests that may be declined or edited
- allows admin to finalize the correct trailer, dates, rates, delivery fee, and deposit before signature
- matches the current request-first workflow

## Front-End Flow
### Step 1: Catalog
No major change beyond optional copy:
- “Request Booking” CTA
- not “Reserve Now” or “Pay Now”

### Step 2: Trailer detail page
Display a booking summary panel with:
- rental rates
- delivery availability
- required refundable deposit
- accepted payment methods
- short notice: “Requests are not confirmed until approved, signed, and paid.”

### Step 3: Booking request form
Keep current reservation-first form.

Add or confirm these fields:
- full name
- company name (optional)
- email
- phone
- requested trailer
- rental start date/time
- rental end date/time
- pickup or delivery
- delivery address if applicable
- preferred payment method: card / ACH / business check
- repeat customer? yes/no
- checkbox: “I understand this is a request, not a confirmed reservation.”

Do **not** ask for signature here.

### Step 4: Admin review
Admin reviews request and either:
- declines
- requests changes
- approves and prepares final terms

Admin must be able to edit before approval:
- trailer assignment
- dates/times
- rental fee
- delivery fee
- deposit amount
- payment method approval
- internal notes

### Step 5: Approval package sent to customer
After approval, customer receives a secure action link to a page that includes:
- booking summary
- rental agreement
- damage fee schedule
- signature fields
- payment instructions or payment link

### Step 6: Signing page
Signing page should show sections in this order:
1. Booking summary
2. Rental agreement
3. Damage fee schedule
4. Required acknowledgments
5. Signature block
6. Next-step payment instructions or payment action

## Required Acknowledgments
Require checkbox acknowledgments before signature:
- I understand this booking is subject to the rental agreement.
- I acknowledge the damage fee schedule.
- I understand I am responsible for damage, misuse, late fees, and cleaning fees.
- I understand the trailer will not be released until payment and deposit requirements are satisfied.

## Signature Requirements
Collect:
- legal full name
- company name if applicable
- typed signature
- signature timestamp
- IP address if available
- email used for booking

Optional but recommended:
- driver’s license number (entered here or captured at pickup)

## Post-Signing Flow
After signature submission:
- store signed contract snapshot/PDF
- mark booking as `SIGNED_AWAITING_PAYMENT` or `SIGNED_AWAITING_CHECK_CLEARANCE` depending on payment type
- email signed copy to customer
- make signed copy visible in admin

## Payment-Specific Branching
### Card
After signature, immediately show payment page or payment button.
Status progression:
- `APPROVED_AWAITING_SIGNATURE`
- `SIGNED_AWAITING_PAYMENT`
- `PAYMENT_RECEIVED_AWAITING_DEPOSIT` or directly `CONFIRMED` if payment+deposit both complete

### ACH
After signature, show ACH payment instructions or invoice sent notice.
Status progression:
- `APPROVED_AWAITING_SIGNATURE`
- `SIGNED_AWAITING_PAYMENT`
- `CONFIRMED` only after admin marks ACH received

### Business check
After signature, show instructions that booking is held pending check receipt/clearance.
Status progression:
- `APPROVED_AWAITING_SIGNATURE`
- `SIGNED_AWAITING_CHECK_CLEARANCE`
- `CONFIRMED` only after admin marks cleared

## Admin Requirements
Admin must be able to:
- view unsigned vs signed requests
- resend signature link
- regenerate signing package if booking terms change before signing
- view executed agreement and damage schedule acknowledgment
- manually mark payment received / check cleared / deposit received
- manually confirm booking
- record pickup and return inspection status

## Legal/Content Handling
- Signed version must be immutable after execution.
- If booking terms change after signing, require a new signing package.
- The executed agreement should store the exact text version presented to the customer.

## MVP Scope
### In scope
- booking approval -> contract signing -> payment readiness flow
- embedded contract display
- acknowledgments
- e-sign capture
- signed PDF generation
- admin visibility
- email notifications
- status tracking

### Out of scope for MVP
- DocuSign integration
- reusable master contractor agreements
- multi-signer flows
- witness/notary features
- advanced identity verification

## Success Criteria
The feature is successful when:
- every confirmed booking has a signed agreement attached
- every signed agreement includes acknowledgment of the damage fee schedule
- admin can easily see which requests are waiting on signature
- customers clearly understand booking is not confirmed until completion
- the signing flow adds protection without creating major friction
