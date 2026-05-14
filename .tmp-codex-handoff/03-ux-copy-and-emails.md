# UX Copy, Form Fields, and Email Templates
**Project:** BFam Rentals / bohachickrentals.com

## 1. Catalog card copy
### Product metadata
- Starting at `$160/day`
- Refundable deposit `$750`
- `Pickup available`
- `Delivery available`

### CTA
`Request Booking`

## 2. Product page copy block
### Booking information
**How booking works**  
Submit a rental request online. We’ll review availability and send you a confirmation link with payment, deposit, and rental agreement steps.

**Important:** Submitting a request does not guarantee availability and is not a confirmed reservation.

### Payment methods
We accept:
- credit/debit card
- ACH
- approved business checks

Business checks must be approved in advance and clear before pickup.

### Security deposit
A refundable security deposit is required for all rentals and may be used for damage, late fees, cleaning, or missing equipment.

## 3. Booking form labels
- First name
- Last name
- Company name (optional)
- Email
- Phone
- Rental start
- Rental end
- Pickup or delivery
- Delivery address
- Preferred payment method
- Are you a repeat contractor account?
- Tow vehicle year
- Tow vehicle make
- Tow vehicle model
- Tow vehicle tow rating
- Brake controller installed?

### Payment method options
- Card
- ACH
- Business check (approved contractor accounts only)

### Form helper text
For pickup rentals, please provide the tow vehicle details you plan to use.

### Required checkbox
`I understand this is a booking request only and is not a confirmed reservation.`

## 4. Request confirmation page
### Heading
Request received

### Body
Thanks for your request. We’ll review availability and send the next steps by email.

This is not yet a confirmed reservation. Your booking is confirmed only after approval, signed rental agreement, payment, and deposit completion.

## 5. Approved booking page
### Heading
Complete your booking

### Sections
- Trailer
- Rental dates
- Rental total
- Delivery fee
- Refundable deposit
- Payment method
- Rental agreement

### Button labels
- `Sign Agreement`
- `Pay Now`
- `View Invoice`
- `Submit ACH Payment`
- `I’ll Pay by Approved Business Check`

### Warning text
Your trailer will not be released until payment, deposit, and signed agreement are complete.

## 6. Pickup instructions copy
Before pickup, please bring:
- valid driver’s license
- the tow vehicle listed on your request
- proof of business identity if renting under a company account

For safety, we’ll verify hitch and tow vehicle compatibility before release.

## 7. Email templates

### A. Request received
**Subject:** We received your rental request

Hi {{firstName}},

Thanks for your rental request for the {{productName}} from {{startDate}} to {{endDate}}.

We’re reviewing availability now. This message confirms that we received your request, but it is not yet a confirmed reservation.

If approved, we’ll send:
- your booking summary
- the rental agreement
- payment and deposit instructions
- pickup or delivery details

Thanks,  
BFam Rentals

---

### B. Request approved
**Subject:** Your rental request was approved — complete your booking

Hi {{firstName}},

Your request for the {{productName}} has been approved.

To confirm your booking, please complete the following:
1. Sign the rental agreement
2. Pay the rental balance
3. Secure the refundable deposit

Booking summary:
- Trailer: {{productName}}
- Dates: {{startDate}} to {{endDate}}
- Rental total: {{rentalTotal}}
- Delivery fee: {{deliveryFee}}
- Refundable deposit: {{depositAmount}}

Complete your booking here: {{approvalUrl}}

Your trailer will not be released until all steps are complete.

Thanks,  
BFam Rentals

---

### C. Contractor check instructions
**Subject:** Approved rental — business check instructions

Hi {{firstName}},

Your rental request for the {{productName}} has been approved pending payment clearance.

We accept business checks only for approved contractor rentals. Please note:
- personal checks are not accepted
- the trailer will not be released until funds are received and cleared
- a card-backed security deposit is still required
- the rental agreement must still be signed before release

Booking summary:
- Trailer: {{productName}}
- Dates: {{startDate}} to {{endDate}}
- Rental total: {{rentalTotal}}
- Refundable deposit: {{depositAmount}}

Next steps:
1. Sign the rental agreement here: {{agreementUrl}}
2. Submit your deposit here: {{depositUrl}}
3. Deliver or mail payment according to the invoice instructions: {{invoiceUrl}}

Thanks,  
BFam Rentals

---

### D. Booking confirmed
**Subject:** Your rental is confirmed

Hi {{firstName}},

Your booking is confirmed.

Rental details:
- Trailer: {{productName}}
- Dates: {{startDate}} to {{endDate}}
- Pickup/Delivery: {{fulfillmentMethod}}

{{pickupOrDeliveryInstructions}}

Please contact us if anything changes before your rental start time.

Thanks,  
BFam Rentals

---

### E. Return reminder
**Subject:** Reminder: your trailer is due back soon

Hi {{firstName}},

This is a reminder that your rental for the {{productName}} is due back on {{endDate}}.

If you need to request an extension, contact us before the return time to avoid late fees.

Thanks,  
BFam Rentals

---

### F. Deposit released
**Subject:** Your deposit has been released

Hi {{firstName}},

Your rental for the {{productName}} has been closed and your security deposit has been released.

Thank you for renting with BFam Rentals.

---

### G. Additional charges notice
**Subject:** Post-rental charges for your booking

Hi {{firstName}},

We completed the return inspection for your rental of the {{productName}}.

Additional charges were applied for:
{{chargeReasonList}}

Total additional charges: {{chargeTotal}}

If you have any questions, please reply to this email.

Thanks,  
BFam Rentals

## 8. Policy copy for site footer / FAQ
### Booking policy
Submitting a booking request does not guarantee availability. Reservations are confirmed only after approval, signed rental agreement, payment, and deposit completion.

### Payment policy
We accept card, ACH, and approved business checks. Business checks must clear before pickup.

### Deposit policy
A refundable security deposit is required for all rentals and may be used for damage, late fees, cleaning, missing items, or unpaid charges.

### Contractor policy
Contractor accounts may request ACH or business check payment. Approval is required, and a card-backed security deposit is still required before release.
