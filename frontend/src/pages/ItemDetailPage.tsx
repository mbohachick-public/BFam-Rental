import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  apiDelete,
  apiGet,
  apiPost,
  apiPostFormData,
  uploadBookingFileToSignedUrl,
} from '../api/client'
import { useCustomerSession } from '../context/CustomerSessionContext'
import { MonthCalendar } from '../components/MonthCalendar'
import { StatusLegend } from '../components/StatusLegend'
import { firstOfMonth, lastOfMonth } from '../lib/calendar'
import type {
  BookingPresignResponse,
  BookingQuote,
  BookingRequestOut,
  CustomerContactProfile,
  DayAvailability,
  ItemDetail,
} from '../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function ItemDetailPage() {
  const customer = useCustomerSession()
  const customerSignedIn = customer.mode === 'auth0' && customer.isAuthenticated
  const { id } = useParams<{ id: string }>()
  const [item, setItem] = useState<ItemDetail | null>(null)
  const [days, setDays] = useState<DayAvailability[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const now = new Date()
  const [calYear, setCalYear] = useState(now.getFullYear())
  const [calMonth, setCalMonth] = useState(now.getMonth() + 1)

  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [address, setAddress] = useState('')
  const [taxZip, setTaxZip] = useState('')
  const [notes, setNotes] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [towYear, setTowYear] = useState('')
  const [towMake, setTowMake] = useState('')
  const [towModel, setTowModel] = useState('')
  const [towRating, setTowRating] = useState('')
  const [hasBrakeController, setHasBrakeController] = useState(false)
  const [requestAck, setRequestAck] = useState(false)
  const [deliveryRequested, setDeliveryRequested] = useState(false)
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [quote, setQuote] = useState<BookingQuote | null>(null)
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const [quoting, setQuoting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitOk, setSubmitOk] = useState<string | null>(null)
  const [driversLicenseFile, setDriversLicenseFile] = useState<File | null>(null)
  const [licensePlateFile, setLicensePlateFile] = useState<File | null>(null)
  const [activeImageIdx, setActiveImageIdx] = useState(0)

  const sortedImages = useMemo(
    () => (item ? [...item.images].sort((a, b) => a.sort_order - b.sort_order) : []),
    [item],
  )

  useEffect(() => {
    setDriversLicenseFile(null)
    setLicensePlateFile(null)
    setFirstName('')
    setLastName('')
    setAddress('')
    setTaxZip('')
    setActiveImageIdx(0)
    setCompanyName('')
    setTowYear('')
    setTowMake('')
    setTowModel('')
    setTowRating('')
    setHasBrakeController(false)
    setRequestAck(false)
    setDeliveryRequested(false)
    setDeliveryAddress('')
  }, [id])

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGet<ItemDetail>(`/items/${id}`)
      .then((data) => {
        if (!cancelled) {
          setItem(data)
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  const fromTo = useMemo(
    () => ({
      from: firstOfMonth(calYear, calMonth),
      to: lastOfMonth(calYear, calMonth),
    }),
    [calYear, calMonth],
  )

  const loadAvailability = useCallback(() => {
    if (!id) return
    const q = new URLSearchParams({ from: fromTo.from, to: fromTo.to }).toString()
    apiGet<DayAvailability[]>(`/items/${id}/availability?${q}`)
      .then(setDays)
      .catch(() => setDays([]))
  }, [id, fromTo.from, fromTo.to])

  useEffect(() => {
    loadAvailability()
  }, [loadAvailability])

  useEffect(() => {
    if (!customerSignedIn || !id) return
    let cancelled = false
    apiGet<CustomerContactProfile>('/booking-requests/me/contact')
      .then((p) => {
        if (cancelled) return
        setEmail((prev) => (prev.trim() ? prev : p.customer_email))
        setPhone((prev) => (prev.trim() ? prev : p.customer_phone))
        setFirstName((prev) => (prev.trim() ? prev : p.customer_first_name))
        setLastName((prev) => (prev.trim() ? prev : p.customer_last_name))
        setAddress((prev) => (prev.trim() ? prev : p.customer_address))
      })
      .catch(() => {
        /* 404 = no prior bookings */
      })
    return () => {
      cancelled = true
    }
  }, [id, customerSignedIn])

  useEffect(() => {
    if (item && item.delivery_available === false) {
      setDeliveryRequested(false)
      setDeliveryAddress('')
      setQuote(null)
    }
  }, [item])

  function shiftMonth(delta: number) {
    const d = new Date(calYear, calMonth - 1 + delta, 1)
    setCalYear(d.getFullYear())
    setCalMonth(d.getMonth() + 1)
  }

  async function getQuote() {
    if (!id || !startDate || !endDate) {
      setQuoteError('Choose a start and end date.')
      return
    }
    const em = email.trim()
    if (!em) {
      setQuoteError('Email is required — we will send your quote there.')
      return
    }
    if (item?.delivery_available && deliveryRequested && !deliveryAddress.trim()) {
      setQuoteError('Enter a delivery address to include delivery on the quote.')
      return
    }
    setQuoteError(null)
    setQuote(null)
    setQuoting(true)
    try {
      const zip = taxZip.trim()
      const q = await apiPost<BookingQuote>('/booking-requests/quote', {
        item_id: id,
        start_date: startDate,
        end_date: endDate,
        customer_email: em,
        ...(zip ? { tax_postal_code: zip } : {}),
        ...(item?.delivery_available && deliveryRequested
          ? { delivery_requested: true, delivery_address: deliveryAddress.trim() }
          : { delivery_requested: false }),
      })
      setQuote(q)
    } catch (e) {
      setQuoteError(e instanceof Error ? e.message : 'Quote failed')
    } finally {
      setQuoting(false)
    }
  }

  async function submitRequest() {
    if (!id || !startDate || !endDate || !item) return
    if (!driversLicenseFile) {
      setQuoteError('Please upload a photo of your driver’s license.')
      return
    }
    if (item.towable && !licensePlateFile) {
      setQuoteError('This item is towable — please upload a photo of your vehicle’s license plate.')
      return
    }
    const em = email.trim()
    const ph = phone.trim()
    const fn = firstName.trim()
    const ln = lastName.trim()
    const addr = address.trim()
    if (!em) {
      setQuoteError('Email is required.')
      return
    }
    if (ph.length < 7) {
      setQuoteError('Please enter a valid phone number (at least 7 digits).')
      return
    }
    if (!fn || !ln || !addr) {
      setQuoteError('First name, last name, and address are required (correct auto-fill if needed).')
      return
    }
    if (!requestAck) {
      setQuoteError('Please confirm that this is a booking request, not a guaranteed reservation.')
      return
    }
    if (item.delivery_available && deliveryRequested && !deliveryAddress.trim()) {
      setQuoteError('Delivery address is required when delivery is requested.')
      return
    }
    if (item.towable) {
      const y = parseInt(towYear, 10)
      if (!towYear.trim() || !Number.isFinite(y)) {
        setQuoteError('Tow vehicle year is required for towable pickup rentals.')
        return
      }
      if (y < 1950 || y > 2100) {
        setQuoteError('Tow vehicle year must be between 1950 and 2100.')
        return
      }
      if (!towMake.trim() || !towModel.trim()) {
        setQuoteError('Tow vehicle make and model are required for towable pickup rentals.')
        return
      }
      const r = parseInt(towRating, 10)
      if (!towRating.trim() || !Number.isFinite(r) || r < 1) {
        setQuoteError('Tow vehicle tow rating (lbs) is required for towable pickup rentals.')
        return
      }
    }
    setSubmitting(true)
    setSubmitOk(null)
    setQuoteError(null)
    const submitMultipart = async () => {
      const fd = new FormData()
      fd.append('item_id', id)
      fd.append('start_date', startDate)
      fd.append('end_date', endDate)
      fd.append('customer_email', em)
      fd.append('customer_phone', ph)
      fd.append('customer_first_name', fn)
      fd.append('customer_last_name', ln)
      fd.append('customer_address', addr)
      if (notes.trim()) fd.append('notes', notes.trim())
      fd.append('drivers_license', driversLicenseFile)
      if (item.towable && licensePlateFile) {
        fd.append('license_plate', licensePlateFile)
      }
      if (item.delivery_available && deliveryRequested) {
        fd.append('delivery_requested', 'true')
        fd.append('delivery_address', deliveryAddress.trim())
      }
      if (item.towable) {
        fd.append('tow_vehicle_year', String(parseInt(towYear, 10)))
        fd.append('tow_vehicle_make', towMake.trim())
        fd.append('tow_vehicle_model', towModel.trim())
        fd.append('tow_vehicle_tow_rating_lbs', String(parseInt(towRating, 10)))
        fd.append('has_brake_controller', hasBrakeController ? 'true' : 'false')
      }
      await apiPostFormData('/booking-requests', fd)
    }
    try {
      const dlType = driversLicenseFile.type || 'image/jpeg'
      const lpType =
        item.towable && licensePlateFile ? licensePlateFile.type || 'image/jpeg' : undefined
      const presignBody: Record<string, unknown> = {
        item_id: id,
        start_date: startDate,
        end_date: endDate,
        customer_email: em,
        customer_phone: ph,
        customer_first_name: fn,
        customer_last_name: ln,
        customer_address: addr,
        notes: notes.trim() || undefined,
        drivers_license_content_type: dlType,
        license_plate_content_type: lpType,
        request_not_confirmed_ack: true,
        company_name: companyName.trim() || undefined,
      }
      if (item.towable) {
        presignBody.tow_vehicle_year = parseInt(towYear, 10)
        presignBody.tow_vehicle_make = towMake.trim()
        presignBody.tow_vehicle_model = towModel.trim()
        presignBody.tow_vehicle_tow_rating_lbs = parseInt(towRating, 10)
        presignBody.has_brake_controller = hasBrakeController
      }
      if (item.delivery_available) {
        presignBody.delivery_requested = deliveryRequested
        presignBody.delivery_address = deliveryRequested ? deliveryAddress.trim() : undefined
      }
      try {
        const pre = await apiPost<BookingPresignResponse>('/booking-requests/presign', presignBody)
        try {
          await uploadBookingFileToSignedUrl(pre.drivers_license.signed_url, driversLicenseFile, dlType)
          if (pre.license_plate && licensePlateFile) {
            await uploadBookingFileToSignedUrl(
              pre.license_plate.signed_url,
              licensePlateFile,
              lpType || 'image/jpeg',
            )
          }
          await apiPost<BookingRequestOut>(`/booking-requests/${pre.booking_id}/complete`, {
            drivers_license_path: pre.drivers_license.path,
            license_plate_path: pre.license_plate?.path ?? null,
          })
        } catch (stepErr) {
          try {
            await apiDelete(`/booking-requests/${pre.booking_id}/abandon`)
          } catch {
            /* best-effort cleanup */
          }
          throw stepErr
        }
      } catch (inner) {
        const m = inner instanceof Error ? inner.message : String(inner)
        if (
          /BOOKING_DOCUMENTS_STORAGE=local|multipart form data|Presigned uploads require/i.test(m)
        ) {
          await submitMultipart()
        } else {
          throw inner
        }
      }
      setSubmitOk('Request submitted. We will follow up when it is reviewed.')
      setQuote(null)
      setDriversLicenseFile(null)
      setLicensePlateFile(null)
    } catch (e) {
      setQuoteError(e instanceof Error ? e.message : 'Submit failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <p className="muted">Loading…</p>
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="container">
        <p className="error-msg">{error ?? 'Not found'}</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  const displayImageIdx =
    sortedImages.length === 0 ? 0 : Math.min(activeImageIdx, sortedImages.length - 1)

  const mainImage =
    sortedImages.length > 0 ? sortedImages[displayImageIdx]?.url : item.image_urls[0]

  const towY = parseInt(towYear, 10)
  const towR = parseInt(towRating, 10)
  const towBookingFieldsIncomplete =
    item.towable &&
    (!towYear.trim() ||
      !towMake.trim() ||
      !towModel.trim() ||
      !towRating.trim() ||
      !Number.isFinite(towY) ||
      towY < 1950 ||
      towY > 2100 ||
      !Number.isFinite(towR) ||
      towR < 1)

  return (
    <div className="container page-item">
      <p className="breadcrumb">
        <Link to="/catalog">Catalog</Link>
        <span aria-hidden> / </span>
        <span>{item.title}</span>
      </p>

      <div className="item-hero">
        <div className="item-gallery card">
          {mainImage ? (
            <img src={mainImage} alt="" className="item-hero-img" />
          ) : (
            <div className="item-hero-placeholder" />
          )}
          {sortedImages.length > 1 && (
            <ul className="item-thumbs">
              {sortedImages.map((im, idx) => (
                <li key={im.id}>
                  <button
                    type="button"
                    className={`item-thumb-btn${idx === displayImageIdx ? ' item-thumb-btn-active' : ''}`}
                    onClick={() => setActiveImageIdx(idx)}
                    aria-pressed={idx === displayImageIdx}
                    aria-label={`View image ${idx + 1} of ${sortedImages.length}`}
                  >
                    <img src={im.url} alt="" loading="lazy" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="item-summary card card-pad">
          <h1>{item.title}</h1>
          <p className="muted">{item.category}</p>
          <dl className="attr-list">
            <div>
              <dt>Cost per day</dt>
              <dd>{money(item.cost_per_day)}</dd>
            </div>
            <div>
              <dt>Minimum rental</dt>
              <dd>
                {item.minimum_day_rental} day{item.minimum_day_rental === 1 ? '' : 's'}
              </dd>
            </div>
            <div>
              <dt>Deposit</dt>
              <dd>{money(item.deposit_amount)}</dd>
            </div>
            <div>
              <dt>Towable</dt>
              <dd>{item.towable ? 'Yes — license plate photo required to book' : 'No'}</dd>
            </div>
            <div>
              <dt>Delivery</dt>
              <dd>
                {item.delivery_available === false
                  ? 'Pickup only at our location'
                  : 'Pickup or delivery may be available — note your preference below'}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <section className="card card-pad section-block">
        <h2>Description</h2>
        <p>{item.description || '—'}</p>
        <h3>User requirements</h3>
        <p>{item.user_requirements || '—'}</p>
      </section>

      <section className="section-block">
        <h2>Availability</h2>
        <p className="muted">Each date has one status. Book only on days marked open.</p>
        <StatusLegend />
        <div className="cal-nav">
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => shiftMonth(-1)}>
            Previous
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => shiftMonth(1)}>
            Next
          </button>
        </div>
        <MonthCalendar year={calYear} month={calMonth} days={days} />
      </section>

      <section className="card card-pad section-block booking-block">
        <h2>Request a booking</h2>
        {customer.mode === 'auth0' && !customer.isLoading && !customer.isAuthenticated && (
          <p className="booking-auth-hint">
            <span className="muted">Sign in to get a quote and submit a booking request.</span>{' '}
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => customer.login()}>
              Sign in
            </button>
          </p>
        )}
        <p className="muted">
          Pick a range within the next 60 days, then upload your license (and plate if towable).
          All days must be open for booking.{' '}
          <strong>Email is required</strong> — we email your quote when you click Get quote (SMTP must
          be configured on the API). License photo: JPEG, PNG, or WebP, max 10 MB.
          {item.towable ? ' Towable rentals also require a photo of your tow vehicle’s license plate.' : ''}
        </p>
        <p className="muted small">
          After approval, rental totals are usually paid with a <strong>secure card checkout</strong>{' '}
          (and a separate deposit link when applicable). The rental team will confirm details.
          Submitting this form is a <strong>request only</strong> — it does not guarantee availability
          until the rental team approves dates, payment, deposit, and agreement.
        </p>
        <form
          className="booking-form"
          autoComplete="on"
          onSubmit={(e) => {
            e.preventDefault()
          }}
        >
        <div className="booking-grid">
          <label className="field">
            <span className="field-label">Start date</span>
            <input
              type="date"
              name="booking_start_date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value)
                setQuote(null)
              }}
            />
          </label>
          <label className="field">
            <span className="field-label">End date</span>
            <input
              type="date"
              name="booking_end_date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value)
                setQuote(null)
              }}
            />
          </label>
          <label className="field field-span">
            <span className="field-label">Driver’s license photo (required)</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setDriversLicenseFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {item.towable && (
            <label className="field field-span">
              <span className="field-label">License plate photo (required for towable)</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setLicensePlateFile(e.target.files?.[0] ?? null)}
              />
            </label>
          )}
          <label className="field field-span">
            <span className="field-label">Email (required)</span>
            <input
              type="email"
              name="customer_email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="section-booking email"
              required
            />
          </label>
          <label className="field">
            <span className="field-label">ZIP for sales tax (optional)</span>
            <input
              type="text"
              name="tax_postal_code"
              inputMode="numeric"
              autoComplete="section-booking postal-code"
              maxLength={10}
              placeholder="e.g. 64089"
              value={taxZip}
              onChange={(e) => {
                setTaxZip(e.target.value)
                setQuote(null)
              }}
            />
          </label>
          <label className="field field-span">
            <span className="field-label">Phone (required)</span>
            <input
              type="tel"
              name="customer_phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="section-booking tel"
              inputMode="tel"
              required
            />
          </label>
          <label className="field">
            <span className="field-label">First name (required)</span>
            <input
              type="text"
              name="customer_first_name"
              id="booking-given-name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              autoComplete="section-booking given-name"
              required
            />
          </label>
          <label className="field">
            <span className="field-label">Last name (required)</span>
            <input
              type="text"
              name="customer_last_name"
              id="booking-family-name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              autoComplete="section-booking family-name"
              required
            />
          </label>
          <label className="field field-span">
            <span className="field-label">Address (required)</span>
            <input
              type="text"
              name="customer_address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              autoComplete="section-booking street-address"
              required
            />
          </label>
          {item.delivery_available ? (
            <>
              <label className="field field-checkbox field-span">
                <input
                  type="checkbox"
                  checked={deliveryRequested}
                  onChange={(e) => {
                    setDeliveryRequested(e.target.checked)
                    setQuote(null)
                  }}
                />
                <span>Request delivery to this address (fee by road miles; shown in quote)</span>
              </label>
              {deliveryRequested ? (
                <label className="field field-span">
                  <span className="field-label">Delivery address</span>
                  <input
                    type="text"
                    name="delivery_address"
                    value={deliveryAddress}
                    onChange={(e) => {
                      setDeliveryAddress(e.target.value)
                      setQuote(null)
                    }}
                    autoComplete="off"
                    placeholder="Where the equipment should be delivered"
                  />
                </label>
              ) : null}
            </>
          ) : null}
          <label className="field field-span">
            <span className="field-label">Notes (optional)</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </label>
          <label className="field field-span">
            <span className="field-label">Company / contractor name (optional)</span>
            <input
              type="text"
              name="customer_company"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              autoComplete="section-booking organization"
            />
          </label>
          {item.towable ? (
            <>
              <label className="field">
                <span className="field-label">Tow vehicle year (required)</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1950}
                  max={2100}
                  required
                  value={towYear}
                  onChange={(e) => setTowYear(e.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">Tow vehicle make (required)</span>
                <input
                  type="text"
                  required
                  value={towMake}
                  onChange={(e) => setTowMake(e.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">Tow vehicle model (required)</span>
                <input
                  type="text"
                  required
                  value={towModel}
                  onChange={(e) => setTowModel(e.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">Tow rating in lbs (required)</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  required
                  value={towRating}
                  onChange={(e) => setTowRating(e.target.value)}
                />
              </label>
              <label className="field field-checkbox field-span">
                <input
                  type="checkbox"
                  checked={hasBrakeController}
                  onChange={(e) => setHasBrakeController(e.target.checked)}
                />
                <span>Brake controller installed on tow vehicle</span>
              </label>
            </>
          ) : null}
          <label className="field field-checkbox field-span">
            <input
              type="checkbox"
              checked={requestAck}
              onChange={(e) => setRequestAck(e.target.checked)}
            />
            <span>
              I understand this is a <strong>request</strong>, not a confirmed reservation, until the
              rental team approves it.
            </span>
          </label>
        </div>
        {quoteError && <p className="error-msg">{quoteError}</p>}
        {submitOk && <p className="success-msg">{submitOk}</p>}
        <div className="booking-actions">
          <button
            type="button"
            className={`btn ${quoting ? 'btn-primary btn-loading' : 'btn-secondary'}`}
            onClick={getQuote}
            disabled={quoting}
            aria-busy={quoting}
          >
            {quoting ? (
              <>
                <svg
                  className="btn-spinner"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  aria-hidden={true}
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    opacity="0.25"
                  />
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray="48"
                    strokeDashoffset="36"
                  />
                </svg>
                Getting quote…
              </>
            ) : (
              'Get quote'
            )}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={submitRequest}
            disabled={
              quoting ||
              submitting ||
              !quote ||
              !driversLicenseFile ||
              (item.towable ? !licensePlateFile : false) ||
              !email.trim() ||
              phone.trim().length < 7 ||
              !firstName.trim() ||
              !lastName.trim() ||
              !address.trim() ||
              !requestAck ||
              (item.delivery_available && deliveryRequested && !deliveryAddress.trim()) ||
              towBookingFieldsIncomplete
            }
          >
            {submitting ? 'Sending…' : 'Submit Booking'}
          </button>
        </div>
        </form>
        {quote && (
          <div className="quote card card-pad">
            <h3>Quote</h3>
            {quote.email_sent ? (
              <p className="success-msg small">We emailed this quote to {email.trim()}.</p>
            ) : (
              <p className="muted small">
                Quote not emailed — configure SMTP on the API (see backend README) to receive it by
                email.
              </p>
            )}
            <ul className="quote-lines">
              <li>
                <span>Days</span>
                <span>{quote.num_days}</span>
              </li>
              <li>
                <span>Rental subtotal</span>
                <span>{money(quote.discounted_subtotal)}</span>
              </li>
              {quote.delivery_fee != null && Number(quote.delivery_fee) > 0 ? (
                <li>
                  <span>
                    Delivery
                    {quote.delivery_distance_miles != null &&
                    quote.delivery_distance_miles !== '' ? (
                      <span className="muted">
                        {' '}
                        (~{Number(quote.delivery_distance_miles)} mi one-way)
                      </span>
                    ) : null}
                  </span>
                  <span>{money(quote.delivery_fee)}</span>
                </li>
              ) : null}
              <li>
                <span>
                  Sales tax ({Number(quote.sales_tax_rate_percent)}%)
                </span>
                <span>{money(quote.sales_tax_amount)}</span>
              </li>
              <li>
                <span>Rental total (with tax)</span>
                <span>{money(quote.rental_total_with_tax)}</span>
              </li>
              <li>
                <span>Deposit (hold)</span>
                <span>{money(quote.deposit_amount)}</span>
              </li>
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
