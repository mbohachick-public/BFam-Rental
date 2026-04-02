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

export interface BookingQuote {
  num_days: number
  base_amount: string
  discount_percent: string
  discounted_subtotal: string
  deposit_amount: string
}

export interface BookingRequestOut {
  id: string
  item_id: string
  start_date: string
  end_date: string
  status: BookingRequestStatus
  customer_email: string | null
  notes: string | null
  base_amount: string | null
  discount_percent: string | null
  discounted_subtotal: string | null
  deposit_amount: string | null
  drivers_license_url?: string | null
  license_plate_url?: string | null
}
