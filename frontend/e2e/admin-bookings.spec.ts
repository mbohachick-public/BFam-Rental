import { test, expect, loginAsAdmin, futureDate, tinyJpeg, API_BASE } from './fixtures'

test.describe('Admin bookings', () => {
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
    await expect(row.getByText(/pending/i)).toBeVisible()
    await expect(row.getByText(start)).toBeVisible()
    await expect(row.getByText(end)).toBeVisible()
  })

  test('accept a pending booking', async ({ page, api }) => {
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

    await page.goto('/admin/bookings')
    const row = page.locator('.admin-booking-row', { hasText: acceptEmail })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await row.getByRole('button', { name: /^Accept$/ }).click()

    // After accepting, status should change
    await expect(row.getByText(/^accepted$/i)).toBeVisible({ timeout: 15_000 })
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
    await expect(row.getByText(/rejected/i)).toBeVisible({ timeout: 10_000 })
  })
})
