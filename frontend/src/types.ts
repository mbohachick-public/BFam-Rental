export type DayStatus =
  | 'out_for_use'
  | 'booked'
  | 'open_for_booking'
  | 'readying_for_use'

export type BookingRequestStatus = 'pending' | 'accepted' | 'rejected'

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
  sales_tax_rate_percent: string
  sales_tax_amount: string
  rental_total_with_tax: string
  sales_tax_source: string
  email_sent?: boolean
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
  expires_in: number
}

export interface BookingRequestOut {
  id: string
  item_id: string
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
}
