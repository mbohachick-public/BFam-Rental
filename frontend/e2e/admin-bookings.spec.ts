import { test, expect, loginAsAdmin, futureDate, tinyJpeg, API_BASE, E2E_ADMIN_AUTH_ENABLED } from './fixtures'

test.describe('Admin bookings', () => {
  test.beforeAll((_worker, testInfo) => {
    testInfo.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN (and backend Auth0 + admin rules)')
  })

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('bookings page renders', async ({ page }) => {
    await page.goto('/admin/bookings')
    await expect(page.getByRole('heading', { name: /booking requests/i })).toBeVisible()
  })

  test('empty state message when no bookings', async ({ page }) => {
    // We can't guarantee empty, but the page should render either rows or empty text
    await page.goto('/admin/bookings')
    const rows = page.locator('.admin-table-row')
    const empty = page.getByText(/no requests yet/i)
    const either = (await rows.count()) > 0 || (await empty.isVisible())
    expect(either).toBeTruthy()
  })

  test('booking row shows status, dates, customer info', async ({ page, api }) => {
    // Multipart POST requires API BOOKING_DOCUMENTS_STORAGE=local (default dev); production uses presign + complete.
    // Create a bookable item and submit a booking via API
    const item = await api.createItem({ towable: false })
    const itemId = item.id as string
    const start = futureDate(5)
    const end = futureDate(7)
    const rowEmail = `row-e2e-${Date.now()}@test.com`

    await api.setDayStatuses(itemId, [
      { day: futureDate(5), status: 'open_for_booking' },
      { day: futureDate(6), status: 'open_for_booking' },
      { day: futureDate(7), status: 'open_for_booking' },
    ])

    const bookRes = await page.request.post(`${API_BASE}/booking-requests`, {
      multipart: {
        item_id: itemId,
        start_date: start,
        end_date: end,
        customer_email: rowEmail,
        customer_phone: '5551234567',
        customer_first_name: 'Test',
        customer_last_name: 'User',
        customer_address: '123 E2E Street',
        drivers_license: {
          name: 'license.jpg',
          mimeType: 'image/jpeg',
          buffer: tinyJpeg(),
        },
      },
    })
    const bookErr = await bookRes.text()
    expect(bookRes.status(), `Booking failed: ${bookErr}`).toBe(201)

    await page.goto('/admin/bookings')
    const row = page.locator('.admin-booking-row', { hasText: rowEmail })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await expect(row.getByText(/requested/i)).toBeVisible()
    await expect(row.getByText(start)).toBeVisible()
    await expect(row.getByText(end)).toBeVisible()
  })

  test('approve and confirm a requested booking', async ({ page, api }) => {
    // Seed item + booking
    const item = await api.createItem()
    const itemId = item.id as string
    const start = futureDate(10)
    const end = futureDate(11)
    const acceptEmail = `accept-e2e-${Date.now()}@test.com`
    await api.setDayStatuses(itemId, [
      { day: start, status: 'open_for_booking' },
      { day: end, status: 'open_for_booking' },
    ])

    const bookRes = await page.request.post(`${API_BASE}/booking-requests`, {
      multipart: {
        item_id: itemId,
        start_date: start,
        end_date: end,
        customer_email: acceptEmail,
        customer_phone: '5559876543',
        customer_first_name: 'Accept',
        customer_last_name: 'Test',
        customer_address: '456 Accept Ave',
        drivers_license: {
          name: 'dl.jpg',
          mimeType: 'image/jpeg',
          buffer: tinyJpeg(),
        },
      },
    })
    const bookErr = await bookRes.text()
    expect(bookRes.status(), `Booking failed: ${bookErr}`).toBe(201)
    const booking = (await bookRes.json()) as { id: string }
    const bookingId = booking.id

    const approved = await api.approveBookingRequest(bookingId, 'card')
    expect(approved.signing_url, 'approve should return signing_url').toBeTruthy()
    await api.customerSignBooking(approved.signing_url!, acceptEmail, 'Accept Test')

    await page.goto('/admin/bookings')
    const row = page.locator('.admin-booking-row', { hasText: acceptEmail })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await expect(row.getByText(/approved_pending_payment/i)).toBeVisible({ timeout: 15_000 })
    await row.getByRole('button', { name: /mark rental paid/i }).click()
    await row.getByRole('button', { name: /mark deposit secured/i }).click()
    await row.getByRole('button', { name: /confirm booking/i }).click()
    await expect(row.getByText(/^confirmed$/i)).toBeVisible({ timeout: 15_000 })
  })

  test('admin approve moves request to awaiting signature', async ({ page, api }) => {
    const item = await api.createItem()
    const itemId = item.id as string
    const start = futureDate(20)
    const end = futureDate(21)
    const email = `await-sig-${Date.now()}@test.com`
    await api.setDayStatuses(itemId, [
      { day: start, status: 'open_for_booking' },
      { day: end, status: 'open_for_booking' },
    ])

    const bookRes = await page.request.post(`${API_BASE}/booking-requests`, {
      multipart: {
        item_id: itemId,
        start_date: start,
        end_date: end,
        customer_email: email,
        customer_phone: '5550001111',
        customer_first_name: 'Sig',
        customer_last_name: 'Wait',
        customer_address: '1 Wait St',
        drivers_license: {
          name: 'dl.jpg',
          mimeType: 'image/jpeg',
          buffer: tinyJpeg(),
        },
      },
    })
    expect(bookRes.ok()).toBeTruthy()

    await page.goto('/admin/bookings')
    const row = page.locator('.admin-booking-row', { hasText: email })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await row.getByRole('button', { name: /^Approve$/ }).click()
    await expect(row.getByText(/approved_awaiting_signature/i)).toBeVisible({ timeout: 15_000 })
    await expect(row.getByRole('button', { name: /resend signing email/i })).toBeVisible()
    await expect(row.getByRole('button', { name: /copy signing link/i })).toBeEnabled()
  })

  test('decline a pending booking with reason', async ({ page, api }) => {
    const item = await api.createItem()
    const itemId = item.id as string
    const start = futureDate(15)
    const end = futureDate(16)
    await api.setDayStatuses(itemId, [
      { day: start, status: 'open_for_booking' },
      { day: end, status: 'open_for_booking' },
    ])

    const declineEmail = `decline-e2e-${Date.now()}@test.com`
    const bookRes = await page.request.post(`${API_BASE}/booking-requests`, {
      multipart: {
        item_id: itemId,
        start_date: start,
        end_date: end,
        customer_email: declineEmail,
        customer_phone: '5551112222',
        customer_first_name: 'Decline',
        customer_last_name: 'Test',
        customer_address: '789 Decline Dr',
        drivers_license: {
          name: 'dl.jpg',
          mimeType: 'image/jpeg',
          buffer: tinyJpeg(),
        },
      },
    })
    const bookErr = await bookRes.text()
    expect(bookRes.status(), `Booking failed: ${bookErr}`).toBe(201)

    await page.goto('/admin/bookings')
    const row = page.locator('.admin-booking-row', { hasText: declineEmail })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await row.getByRole('button', { name: /decline/i }).click()

    // Decline modal should appear
    const modal = page.locator('.modal-dialog')
    await expect(modal).toBeVisible()

    // Try submitting without a reason
    await modal.getByRole('button', { name: /decline.*notify/i }).click()
    await expect(modal.getByText(/enter a reason/i)).toBeVisible()

    // Fill reason and confirm
    await modal.getByLabel(/reason/i).fill('Equipment under maintenance.')
    await modal.getByRole('button', { name: /decline.*notify/i }).click()

    // Modal should close and status should change
    await expect(modal).not.toBeVisible({ timeout: 10_000 })
    await expect(row.getByText(/declined/i)).toBeVisible({ timeout: 10_000 })
  })
})
