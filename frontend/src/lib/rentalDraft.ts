const DRAFT_KEY = "brs_rental_draft"
const DRAFT_VERSION = 1

export type RentalDraft = {
  itemId: string
  startDate: string
  endDate: string
  deliverToSite: boolean
  pickupFromSite: boolean
  logisticsAddress: string
  customerAddress: string
  email: string
  phone: string
  firstName: string
  lastName: string
  notes: string
  companyName: string
}

type StoredDraft = RentalDraft & { v: number }

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

function asString(v: unknown): string {
  return typeof v === "string" ? v : ""
}

function asBool(v: unknown): boolean {
  return v === true
}

function parseDraft(raw: unknown): RentalDraft | null {
  if (!raw || typeof raw !== "object") return null
  const o = raw as Record<string, unknown>
  if (o.v !== DRAFT_VERSION) return null
  const itemId = asString(o.itemId).trim()
  if (!itemId) return null
  const startDate = asString(o.startDate)
  const endDate = asString(o.endDate)
  if (startDate && !ISO_DAY.test(startDate)) return null
  if (endDate && !ISO_DAY.test(endDate)) return null
  return {
    itemId,
    startDate,
    endDate,
    deliverToSite: asBool(o.deliverToSite),
    pickupFromSite: asBool(o.pickupFromSite),
    logisticsAddress: asString(o.logisticsAddress),
    customerAddress: asString(o.customerAddress),
    email: asString(o.email),
    phone: asString(o.phone),
    firstName: asString(o.firstName),
    lastName: asString(o.lastName),
    notes: asString(o.notes),
    companyName: asString(o.companyName),
  }
}

export function readRentalDraft(): RentalDraft | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    return parseDraft(JSON.parse(raw) as unknown)
  } catch {
    return null
  }
}

export function writeRentalDraft(draft: RentalDraft): void {
  const stored: StoredDraft = { v: DRAFT_VERSION, ...draft }
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(stored))
  } catch {
    /* quota / private mode */
  }
}

export function clearRentalDraft(): void {
  try {
    sessionStorage.removeItem(DRAFT_KEY)
  } catch {
    /* ignore */
  }
}
