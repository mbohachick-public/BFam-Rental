export type DayStatus =
  | 'out_for_use'
  | 'booked'
  | 'open_for_booking'
  | 'readying_for_use'
  | 'pending_request'

export type BookingRequestStatus =
  | 'pending'
  | 'requested'
  | 'pending_approval'
  | 'under_review'
  | 'approved_awaiting_signature'
  | 'approved_pending_payment'
  | 'approved_pending_check_clearance'
  | 'confirmed'
  | 'ready_for_pickup'
  | 'checked_out'
  | 'returned_pending_inspection'
  | 'completed'
  | 'completed_with_charges'
  | 'cancelled'
  | 'declined'
  | 'accepted'
  | 'rejected'

/** Stored on bookings after approve; product uses card (Stripe) only. */
export type PaymentPath = 'card'

/** Matches backend DepositAuthorizationStatus. */
export type DepositAuthorizationStatus = 'not_started' | 'authorized' | 'failed' | 'not_required'

/** POST /booking-requests/intake */
export interface BookingIntakeOut {
  booking_id: string
  complete_path: string
  status: BookingRequestStatus
}

/** GET /booking-requests/:id/completion-summary */
export interface BookingCompletionSummaryOut {
  booking_id: string
  status: BookingRequestStatus
  item_title: string
  start_date: string
  end_date: string
  num_days: number
  towable: boolean
  delivery_requested: boolean
  pickup_from_site_requested: boolean
  discounted_subtotal: string
  deposit_amount: string
  rental_total_with_tax: string
  delivery_fee?: string
  pickup_fee?: string
  damage_waiver_daily_amount?: string
  stripe_payment_collection_enabled: boolean
  rental_terms_url?: string | null
  /** Job site when delivery and/or pickup-from-site was selected */
  logistics_address?: string | null
  delivery_address?: string | null
  job_site_address?: string | null
  /** Customer mailing / billing — collected on Step 1 */
  customer_address?: string | null
}

export interface BookingStripeSetupIntentOut {
  client_secret: string
  publishable_key: string
}

export interface ItemImage {
  id: string
  url: string
  sort_order: number
}

export interface ItemSummary {
  id: string
  title: string
  category: string
  cost_per_day: string
  minimum_day_rental: number
  deposit_amount: string
  towable?: boolean
  /** When true, catalog/detail may show delivery as an option */
  delivery_available?: boolean
  image_urls: string[]
  /** false = hidden from public catalog; admins still see the item */
  active?: boolean
}

export interface ItemDetail extends ItemSummary {
  description: string
  user_requirements: string
  images: ItemImage[]
}

export interface DayAvailability {
  day: string
  status: DayStatus | null
}

/** Response from POST /admin/maintenance/cleanup-e2e-test-data */
export interface E2eCleanupResult {
  items_deleted: number
  bookings_processed_for_file_cleanup: number
}

export interface BookingQuote {
  num_days: number
  base_amount: string
  discount_percent: string
  discounted_subtotal: string
  deposit_amount: string
  delivery_fee?: string
  pickup_fee?: string
  delivery_distance_miles?: string | null
  pickup_distance_miles?: string | null
  sales_tax_rate_percent: string
  sales_tax_amount: string
  rental_total_with_tax: string
  email_sent?: boolean
}

/** GET/PATCH /admin/delivery-settings */
export interface DeliverySettingsOut {
  id: number
  enabled: boolean
  origin_address: string
  price_per_mile: string
  minimum_fee: string
  free_miles: string
  max_delivery_miles?: string | null
  google_maps_configured: boolean
}

/** GET /booking-requests/mine — customer Auth0 only */
export interface CustomerBookingSummary {
  id: string
  item_id: string
  item_title: string
  item_active: boolean
  start_date: string
  end_date: string
  status: BookingRequestStatus
  discounted_subtotal?: string | null
  rental_total_with_tax?: string | null
  deposit_amount?: string | null
  /** Present when the rental team has approved the request and set a pay link */
  payment_collection_url?: string | null
  /** Stripe Checkout URL after admin generates it (card path). */
  stripe_checkout_url?: string | null
  stripe_deposit_checkout_url?: string | null
}

/** GET /booking-requests/mine/:id — customer Auth0 only */
export interface CustomerBookingDetail extends BookingRequestOut {
  item_title: string
  has_executed_contract: boolean
  item_active?: boolean
}

/** GET /booking-requests/me/contact */
export interface CustomerContactProfile {
  customer_email: string
  customer_phone: string
  customer_first_name: string
  customer_last_name: string
  customer_address: string
}

/** POST /booking-requests/presign — direct-to-Supabase upload flow */
export interface BookingUploadSlot {
  path: string
  signed_url: string
  token: string
}

export interface BookingPresignResponse {
  booking_id: string
  drivers_license: BookingUploadSlot
  license_plate: BookingUploadSlot | null
  insurance_card?: BookingUploadSlot | null
  expires_in: number
}

export interface BookingCompletionPresignOut {
  drivers_license: BookingUploadSlot
  insurance_card?: BookingUploadSlot | null
  expires_in: number
}

export interface BookingRequestOut {
  id: string
  item_id: string
  /** Populated on GET /admin/booking-requests/:id */
  item_title?: string | null
  start_date: string
  end_date: string
  status: BookingRequestStatus
  customer_email: string | null
  customer_phone?: string | null
  customer_first_name?: string | null
  customer_last_name?: string | null
  customer_address?: string | null
  notes: string | null
  decline_reason?: string | null
  decline_email_sent?: boolean | null
  base_amount: string | null
  discount_percent: string | null
  discounted_subtotal: string | null
  deposit_amount: string | null
  sales_tax_rate_percent?: string | null
  sales_tax_amount?: string | null
  rental_total_with_tax?: string | null
  sales_tax_source?: string | null
  drivers_license_url?: string | null
  license_plate_url?: string | null
  insurance_card_url?: string | null
  company_name?: string | null
  delivery_address?: string | null
  delivery_requested?: boolean | null
  pickup_from_site_requested?: boolean | null
  delivery_fee?: string | null
  pickup_fee?: string | null
  delivery_distance_miles?: string | null
  pickup_distance_miles?: string | null
  payment_method_preference?: string | null
  is_repeat_contractor?: boolean | null
  tow_vehicle_year?: number | null
  tow_vehicle_make?: string | null
  tow_vehicle_model?: string | null
  tow_vehicle_tow_rating_lbs?: number | null
  has_brake_controller?: boolean | null
  request_not_confirmed_ack?: boolean | null
  payment_path?: string | null
  payment_collection_url?: string | null
  approved_at?: string | null
  rental_paid_at?: string | null
  deposit_secured_at?: string | null
  agreement_signed_at?: string | null
  stripe_invoice_id?: string | null
  stripe_checkout_session_id?: string | null
  stripe_checkout_url?: string | null
  stripe_payment_intent_id?: string | null
  rental_payment_status?: 'unpaid' | 'paid' | 'failed' | 'refunded' | null
  stripe_checkout_created_at?: string | null
  /**
   * Cents of deposit actually captured in Stripe, or 0 / unset when the deposit is only
   * an auth hold (manual capture, separate deposit Checkout) until capture/refund/void.
   * Legacy combined checkout may store the deposit portion in cents.
   */
  stripe_deposit_captured_cents?: number | null
  deposit_refunded_at?: string | null
  stripe_deposit_refund_id?: string | null
  stripe_deposit_checkout_session_id?: string | null
  stripe_deposit_checkout_url?: string | null
  stripe_deposit_checkout_created_at?: string | null
  stripe_deposit_payment_intent_id?: string | null
  agreement_terms_acknowledged?: boolean | null
  request_approval_acknowledged?: boolean | null
  agreement_sign_intent_acknowledged?: boolean | null
  vehicle_tow_capable_ack?: boolean | null
  damage_waiver_selected?: boolean | null
  damage_waiver_daily_amount?: string | null
  damage_waiver_line_total?: string | null
  rental_subtotal_snapshot?: string | null
  stripe_saved_payment_method_id?: string | null
  deposit_authorization_status?: DepositAuthorizationStatus | string | null
  verification_submitted_at?: string | null
  /** Present on admin approve/resend only — copy to customer. */
  signing_url?: string | null
}

export interface StripeCheckoutSessionOut {
  stripe_checkout_session_id?: string | null
  stripe_checkout_url?: string | null
  stripe_checkout_created_at?: string | null
  stripe_deposit_checkout_session_id?: string | null
  stripe_deposit_checkout_url?: string | null
  stripe_deposit_checkout_created_at?: string | null
  /** `sent` | `skipped_no_smtp` | `skipped_no_customer_email` | `skipped_payment_links_in_approval_email` (awaiting signature) | … */
  stripe_checkout_email_status?: string | null
}

/** POST /admin/booking-requests/:id/sync-stripe-checkout */
export interface StripeCheckoutSyncOut {
  actions: string[]
  booking: BookingRequestOut
}

export interface BookingPaymentStatusPublic {
  booking_id: string
  status: string
  rental_paid: boolean
  rental_payment_status?: string | null
  item_title: string
  deposit_secured?: boolean
  requires_deposit?: boolean
}

export interface BookingSignPageOut {
  item_title: string
  start_date: string
  end_date: string
  delivery_address?: string | null
  rental_total_with_tax?: string | null
  deposit_amount?: string | null
  payment_path?: string | null
  customer_first_name?: string | null
  customer_last_name?: string | null
  customer_email?: string | null
  company_name?: string | null
  agreement_html: string
  damage_html: string
  expires_at: string
}

export interface BookingSignResultOut {
  ok: boolean
  next_status: string
  next_url: string
}

export interface ResendSignatureOut {
  signing_url: string
}

export interface BookingSignCompleteOut {
  ok: boolean
  message: string
  booking_id: string
  booking_status?: string | null
  payment_path?: string | null
  stripe_checkout_url?: string | null
  stripe_deposit_checkout_url?: string | null
  rental_balance_paid?: boolean
  deposit_secured?: boolean
}
