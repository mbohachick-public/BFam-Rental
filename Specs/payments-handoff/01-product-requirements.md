# Booking, Payments, Deposits, and Contractor Workflow Spec
**Project:** BFam Rentals / bohachickrentals.com  
**Prepared for:** Codex implementation  
**Date:** 2026-04-16

## 1. Goal
Add a production-ready payment and deposit workflow to the existing website without replacing the current reservation-first UX.

Current state:
- Customer can browse catalog
- Customer can review product details
- Customer can submit a booking/request
- Website does not currently collect payment

Target state:
- Booking request remains the first step
- Admin approves or declines requests
- Approved requests move into a payment + agreement flow
- Business supports both standard retail renters and contractor workflows
- Business supports card, ACH, and approved business checks
- Business enforces deposits before trailer release

## 2. Business model assumptions
This spec assumes:
- Trailer rental only for now
- Trailer classes currently in scope:
  - 14,000 lb 14'–16' dump trailer
  - 7,000 lb 10' dump trailer
  - 7,000 lb 12' dump trailer
  - 18+2 dovetail car hauler
- Customers may either pick up trailers or request delivery
- Website already has a catalog page and booking/request flow
- Website does not need full ecommerce cart behavior
- Admin manually reviews requests before confirmation

## 3. Core design decision
Use a **two-stage flow** instead of forcing payment at the time of request.

### Stage 1: Rental request
The customer submits a request. No reservation is confirmed yet.

### Stage 2: Approval and payment
After admin review, the customer receives:
- approved booking summary
- payment instructions or payment link
- deposit requirement
- rental agreement
- confirmation only after completion

This avoids:
- refunding payments for unavailable inventory
- bad contractor check scenarios
- accidental confirmations before admin review
- overcomplicating the current website

## 4. Customer types
### Standard customer
Usually homeowner or first-time renter.
Rules:
- must pay by card or ACH
- must provide deposit
- must sign agreement before release

### Contractor account
Business renter that may prefer invoice/check.
Rules:
- business checks only
- check accepted only with admin approval
- trailer released only after funds are received and cleared
- card on file still required for deposit / damages
- no personal checks

## 5. Booking statuses
System should support the following statuses:

1. `draft`  
   Optional internal status if admin starts a request manually.

2. `requested`  
   Customer submitted request. No trailer reserved yet.

3. `under_review`  
   Optional status while staff validates availability, logistics, and payment eligibility.

4. `approved_pending_payment`  
   Admin approved request, waiting for payment/deposit/agreement.

5. `approved_pending_check_clearance`  
   For approved contractor bookings waiting on check clearance.

6. `confirmed`  
   Payment complete, deposit secured, agreement signed.

7. `ready_for_pickup`  
   Optional operational status once trailer is staged.

8. `checked_out`  
   Trailer released to customer or dispatched for delivery.

9. `returned_pending_inspection`  
   Trailer returned, inspection underway.

10. `completed`  
   Rental closed, no further charges.

11. `completed_with_charges`  
   Rental closed with post-rental charges.

12. `declined`  
   Request denied.

13. `cancelled`  
   Customer or admin cancelled before checkout.

## 6. Payment methods
### Allowed methods
- Card
- ACH
- Business check with approval

### Not allowed
- Personal checks
- Same-day release against uncleared check
- Unsecured rentals without deposit

## 7. Deposit rules
### Default deposits
- 7K dump trailer: $500
- Car hauler: $500
- 14K dump trailer: $750–$1,000

Recommend initial implementation defaults:
- 14K dump: $750
- 7K dump 10': $500
- 7K dump 12': $500
- 18+2 car hauler: $500

### Deposit usage
Deposit may be used for:
- damage
- late fees
- cleaning
- missing accessories/equipment
- unpaid balance

### Deposit behavior
Preferred:
- card authorization hold

Fallback:
- captured card payment with manual refund after inspection

## 8. Pickup and delivery rules
### Pickup
Before trailer release:
- booking must be confirmed
- ID must be verified
- tow vehicle compatibility must be verified
- signed agreement must be on file
- payment must be completed
- deposit must be secured

### Delivery
Before dispatch:
- booking must be confirmed
- payment must be completed
- deposit must be secured
- signed agreement must be on file
- delivery address confirmed
- delivery fee included in quote

## 9. Website UX changes
### Catalog card
Add:
- daily price
- deposit amount
- pickup / delivery badge
- CTA: `Request Booking`

Do not use `Book Now` unless payment is collected immediately.

### Product detail page
Add visible policy summary:
- rental price structure
- deposit amount
- accepted payment methods
- note that request is not a confirmed reservation
- note that booking is confirmed only after approval, payment, deposit, and agreement

### Booking request form
Required fields:
- first name
- last name
- company name (optional)
- email
- phone
- trailer/product ID
- requested start date
- requested end date
- pickup or delivery
- delivery address if applicable
- preferred payment method
- repeat contractor account yes/no
- tow vehicle details for pickup flows
- agreement acknowledgement checkbox:
  - "I understand this is a request, not a confirmed reservation."

## 10. Approval flow
When admin approves:
- system generates approved quote / booking summary
- system sets status to `approved_pending_payment`
- customer receives:
  - approval email
  - agreement link
  - payment link or invoice
  - deposit requirement
  - pickup or delivery instructions

For check-based contractor workflows:
- set status to `approved_pending_check_clearance`
- send invoice and instructions
- do not release trailer until check is marked cleared by admin

## 11. Confirmation logic
Booking becomes `confirmed` only when:
- approval exists
- required payment received
- deposit secured
- agreement signed

No exceptions in code.

## 12. Admin actions needed
Admin UI should support:
- approve request
- decline request
- select payment method path
- override deposit amount
- mark agreement signed
- mark check received
- mark check cleared
- mark payment received
- mark deposit secured
- mark ready for pickup
- mark checked out
- mark returned
- assess post-rental charges
- refund or release deposit
- close rental

## 13. Notifications
### Customer notifications
1. Request received
2. Request approved
3. Request declined
4. Payment reminder
5. Booking confirmed
6. Pickup instructions
7. Delivery dispatch notice
8. Return reminder
9. Deposit released / refunded
10. Damage / additional charge notice

### Internal notifications
- New request submitted
- Request pending review
- Approved booking still unpaid after X hours
- Check-based booking awaiting clearance
- Pickup scheduled for today
- Return overdue

## 14. Initial rollout scope
### Phase 1
- Request form improvements
- Booking status model
- Admin approval flow
- Stripe payment link / invoice integration
- Agreement tracking
- Manual deposit capture/refund support

### Phase 2
- ACH support
- contractor account tagging
- check-clearance workflow
- automated reminder emails

### Phase 3
- saved contractor payment profiles
- reusable master agreement
- card auth hold automation
- repeat customer self-service account tools

## 15. Non-goals
Do not build yet:
- dynamic route optimization
- full fleet management ERP
- customer-led booking approval
- fully automated trust-based net terms
- equipment rental workflow

## 16. Acceptance summary
The build is successful when:
- request submission does not confirm booking
- admin can approve or decline
- approved requests can collect payment and deposit
- contractor check workflows are supported safely
- no trailer can reach checkout status without payment + deposit + agreement
