# Acceptance Checklist and Implementation Plan
**Project:** BFam Rentals / bohachickrentals.com

## 1. Build order
### Step 1: Data model and migrations
- [ ] Create booking status enum
- [ ] Create bookings table fields for approval/payment/deposit state
- [ ] Create payments table
- [ ] Create deposits table
- [ ] Create agreements table
- [ ] Create booking events table

### Step 2: Public request flow
- [ ] Update product cards with rate/deposit metadata
- [ ] Update product page with booking/payment/deposit policy copy
- [ ] Update booking form with payment preference, contractor flag, and tow vehicle fields
- [ ] Add request acknowledgement checkbox
- [ ] Ensure request submission creates `requested` booking only
- [ ] Send request-received email

### Step 3: Admin review tools
- [ ] Build bookings list for requested/under_review items
- [ ] Build booking detail page
- [ ] Add approve action
- [ ] Add decline action
- [ ] Add approved rate, delivery fee, and deposit override fields
- [ ] Add payment path selector: card / ach / business_check
- [ ] Write booking event logs

### Step 4: Payment + agreement flow
- [ ] Create approved booking page
- [ ] Add agreement signing flow
- [ ] Add Stripe payment link or invoice creation
- [ ] Add deposit collection flow
- [ ] Mark payment complete from webhook or admin action
- [ ] Mark deposit secured
- [ ] Confirm booking only after payment + deposit + agreement

### Step 5: Contractor check flow
- [ ] Add `approved_pending_check_clearance` status
- [ ] Add admin action: mark check received
- [ ] Add admin action: mark check cleared
- [ ] Ensure check path still requires signed agreement
- [ ] Ensure check path still requires card-backed deposit
- [ ] Block confirmation until check cleared

### Step 6: Operations states
- [ ] Add mark-ready action
- [ ] Add checkout action
- [ ] Add return action
- [ ] Add post-rental charge action
- [ ] Add deposit release/refund action
- [ ] Add booking completion action

## 2. Critical acceptance tests
### Request flow
- [ ] Customer can submit request without paying
- [ ] Submitted request is not confirmed automatically
- [ ] Confirmation page clearly says request is not a reservation
- [ ] Email is sent after request submission

### Approval flow
- [ ] Admin can approve with card path
- [ ] Admin can approve with ach path
- [ ] Admin can approve with business_check path
- [ ] Admin can decline request

### Guardrails
- [ ] System blocks `confirmed` if agreement not signed
- [ ] System blocks `confirmed` if deposit not secured
- [ ] System blocks `confirmed` if payment not complete
- [ ] System blocks `checked_out` if booking not confirmed
- [ ] System blocks delivery dispatch unless payment/deposit/agreement complete

### Contractor flow
- [ ] Business check cannot be used without company name
- [ ] Booking remains pending until check cleared
- [ ] Personal check path does not exist
- [ ] Card-backed deposit is still required for approved contractor account

### Deposits
- [ ] Deposit defaults are correct by trailer type
- [ ] Admin can override deposit amount
- [ ] Deposit can be released after inspection
- [ ] Deposit can be partially applied to charges
- [ ] Deposit event history is stored

### Notifications
- [ ] Request received email sends
- [ ] Approved booking email sends
- [ ] Confirmed booking email sends
- [ ] Deposit released email sends
- [ ] Charges notice email sends

## 3. Manual test scenarios
### Scenario 1: Standard pickup renter
- [ ] Request 7K 12' dump trailer
- [ ] Approve for card payment
- [ ] Sign agreement
- [ ] Pay rental fee
- [ ] Secure deposit
- [ ] Confirm booking
- [ ] Checkout succeeds
- [ ] Return and release deposit

### Scenario 2: Delivery rental
- [ ] Request 14K dump trailer with delivery
- [ ] Add delivery fee
- [ ] Pay total and deposit
- [ ] Sign agreement
- [ ] Confirm booking
- [ ] Dispatch allowed
- [ ] Return and close

### Scenario 3: Approved contractor via business check
- [ ] Request car hauler with business check preference
- [ ] Admin approves to check path
- [ ] Agreement signed
- [ ] Deposit secured by card
- [ ] Check received
- [ ] Check cleared
- [ ] Confirm booking
- [ ] Checkout succeeds

### Scenario 4: Contractor tries to skip deposit
- [ ] System blocks confirmation
- [ ] System blocks checkout

### Scenario 5: Request declined
- [ ] Request created
- [ ] Admin declines
- [ ] Customer receives decline notice
- [ ] No payment page remains active

## 4. Nice-to-have follow-ups after MVP
- [ ] saved contractor accounts
- [ ] reusable master agreement
- [ ] automated reminders
- [ ] self-service rescheduling
- [ ] card authorization hold instead of manual capture/refund
- [ ] damage photo upload on return
