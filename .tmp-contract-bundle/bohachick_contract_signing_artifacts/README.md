# Codex Handoff: Contract + E-Sign Flow for BFam Rentals

This bundle adds the rental agreement and damage fee schedule into the current website workflow.

## Included Files
1. `01-contract-signing-product-spec.md`
2. `02-contract-signing-technical-spec.md`
3. `03-contract-signing-ux-copy.md`
4. `04-contract-signing-acceptance-checklist.md`

## Build Goal
Preserve the current request-first booking model and add a post-approval contract-signing workflow that:
- presents the rental agreement
- presents the damage fee schedule
- captures acknowledgment + typed electronic signature
- stores an executed contract packet
- updates booking status through signature/payment/confirmation stages

## Suggested Prompt for Codex
Use the attached specs to implement a contract-signing workflow for bohachickrentals.com.

Constraints:
- preserve the existing catalog -> trailer detail -> booking request flow
- do not convert the request form into a full ecommerce checkout
- signing happens only after admin approval
- include both the rental agreement and damage fee schedule in the signing packet
- generate an executed PDF packet after signing
- track booking statuses exactly as described in the spec
- require re-signing if booking terms change after packet generation
- expose admin controls for resend/regenerate/mark payment received/confirm

Implementation priorities:
1. data model updates
2. admin approval + packet generation
3. customer signing page
4. executed PDF storage
5. status transitions
6. email notifications
7. acceptance tests

## Notes
This is designed as an MVP-friendly internal e-sign flow rather than a DocuSign-style integration.
