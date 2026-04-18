# BFam Rentals Contract + E-Sign Acceptance Checklist

## Booking Request Stage
- [ ] Trailer detail page explains that requests are not confirmed until approval, signing, and payment/deposit completion.
- [ ] Booking form includes payment method selection.
- [ ] Booking form includes acknowledgment that submission is only a request.
- [ ] Booking requests are created with `REQUEST_SUBMITTED` or `PENDING_REVIEW` status.

## Admin Approval Stage
- [ ] Admin can edit final booking terms before approval.
- [ ] Admin approval generates immutable document snapshots.
- [ ] Admin approval creates a signing token/link.
- [ ] Admin approval sends an email with signing instructions.
- [ ] Booking status changes to `APPROVED_AWAITING_SIGNATURE`.

## Signing Stage
- [ ] Sign page shows booking summary.
- [ ] Sign page shows full rental agreement text.
- [ ] Sign page shows full damage fee schedule text.
- [ ] Sign page requires all acknowledgment checkboxes.
- [ ] Sign page requires typed signature.
- [ ] Successful sign submission stores timestamp and signer identity details.
- [ ] Successful sign submission creates an executed PDF packet.
- [ ] Signed PDF is attached to the booking.
- [ ] Customer receives confirmation email with signed packet.

## Payment Branching
- [ ] Card bookings move to `SIGNED_AWAITING_PAYMENT` after signature.
- [ ] ACH bookings move to `SIGNED_AWAITING_PAYMENT` after signature.
- [ ] Check bookings move to `SIGNED_AWAITING_CHECK_CLEARANCE` after signature.
- [ ] Admin can manually mark ACH received.
- [ ] Admin can manually mark check cleared.
- [ ] Admin can manually mark deposit received when needed.
- [ ] Booking can move to `CONFIRMED` only after signature and required payment/deposit conditions are satisfied.

## Admin Controls
- [ ] Admin can view whether a booking has been signed.
- [ ] Admin can download/view executed packet.
- [ ] Admin can resend sign link.
- [ ] Admin can regenerate packet if terms change before signing.
- [ ] Admin cannot silently modify an already executed contract packet.

## Edge Cases
- [ ] Expired signing links show a clear error and recovery path.
- [ ] Old signing links are invalid after packet regeneration.
- [ ] Booking term changes after signing require re-signing.
- [ ] Duplicate submissions do not create conflicting signature records.

## Operational Gate
- [ ] Pickup workflow clearly blocks release unless booking is `CONFIRMED`.
- [ ] Admin/pickup team can easily verify executed agreement exists before release.
