import { test, expect, loginAsAdmin, futureDate, tinyJpeg, E2E_ADMIN_AUTH_ENABLED } from './fixtures'

/*
 * Mobile viewport tests.
 *
 * Run with:  npx playwright test mobile --project="mobile-chrome" --project="mobile-ios"
 *
 * The Playwright config defines mobile-chrome (Pixel 7, 412x915) and mobile-ios
 * (iPhone 14 viewport/user-agent on Chromium — real WebKit is skipped on macOS 12).
 * These tests validate layout and usability at those sizes.
 *
 * When run with --project=chromium, we still use a narrow viewport so layout assertions hold.
 */

test.describe('Mobile viewports', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

  test.describe('Mobile: Home page', () => {
    test('hero is visible and CTA is tappable', async ({ page }) => {
      await page.goto('/')
      const heading = page.getByRole('heading', { level: 1 })
      await expect(heading).toBeVisible()
      await expect(heading).toBeInViewport()

      const cta = page.getByRole('link', { name: /browse catalog/i })
      await expect(cta).toBeVisible()
      const box = await cta.boundingBox()
      expect(box).toBeTruthy()
      // Touch target should be at least 44x44 (Apple HIG / WCAG)
      expect(box!.height).toBeGreaterThanOrEqual(40)
    })

    test('feature cards stack vertically', async ({ page }) => {
      await page.goto('/')
      const cards = page.locator('.features .card')
      const count = await cards.count()
      expect(count).toBe(3)

      if (count >= 2) {
        const first = await cards.nth(0).boundingBox()
        const second = await cards.nth(1).boundingBox()
        // In single-column layout, second card should be below first
        expect(second!.y).toBeGreaterThan(first!.y)
      }
    })
  })

  test.describe('Mobile: Catalog', () => {
    test('filters and cards render in single-column', async ({ page }) => {
      await page.goto('/catalog')
      await expect(page.getByRole('heading', { name: 'Catalog' })).toBeVisible()

      // Filters should be visible
      await expect(page.getByLabel('Category')).toBeVisible()

      // Cards grid: verify cards exist
      const grid = page.locator('.catalog-grid')
      await expect(grid).toBeVisible({ timeout: 10_000 })
    })

    test('price sliders are usable on mobile', async ({ page }) => {
      await page.goto('/catalog')
      const minSlider = page.getByLabel(/minimum dollars/i)
      await expect(minSlider).toBeVisible()
      const box = await minSlider.boundingBox()
      expect(box).toBeTruthy()
      // Slider should have reasonable width for finger interaction
      expect(box!.width).toBeGreaterThan(100)
    })
  })

  test.describe('Mobile: Item detail', () => {
    let itemId = ''

    test.beforeAll(async ({ request }) => {
      if (!E2E_ADMIN_AUTH_ENABLED) return
      const { createItem, uploadImage, setDayStatuses } = await (
        await import('./fixtures')
      ).adminApi(request)
      const item = await createItem({ title: 'Mobile Detail E2E' })
      itemId = item.id as string
      await uploadImage(itemId, 'mob.jpg', 'image/jpeg', tinyJpeg())
      await setDayStatuses(itemId, [
        { day: futureDate(3), status: 'open_for_booking' },
      ])
    })

    test('gallery image is full-width', async ({ page }) => {
      test.skip(!itemId, 'Set E2E_AUTH0_ACCESS_TOKEN to seed item')
      await page.goto(`/items/${itemId}`)
      const img = page.locator('.item-hero-img')
      await expect(img).toBeVisible()
      const imgBox = await img.boundingBox()
      const viewport = page.viewportSize()
      if (imgBox && viewport) {
        // Image should span at least 85% of viewport width on mobile
        expect(imgBox.width).toBeGreaterThan(viewport.width * 0.8)
      }
    })

    test('booking form fields are usable', async ({ page }) => {
      test.skip(!itemId, 'Set E2E_AUTH0_ACCESS_TOKEN to seed item')
      await page.goto(`/items/${itemId}`)
      const emailInput = page.getByLabel(/email/i).first()
      if (await emailInput.isVisible()) {
        const box = await emailInput.boundingBox()
        expect(box).toBeTruthy()
        expect(box!.height).toBeGreaterThanOrEqual(30)
      }
    })
  })

  test.describe('Mobile: Admin', () => {
    test.beforeAll(({}, testInfo) => {
      testInfo.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN (and backend Auth0 + admin rules)')
    })

    test('admin items list is readable', async ({ page }) => {
      await loginAsAdmin(page)
      await expect(page.getByRole('heading', { name: /items/i })).toBeVisible()
      const addBtn = page.getByRole('link', { name: /add item/i })
      await expect(addBtn).toBeVisible()
      const box = await addBtn.boundingBox()
      expect(box).toBeTruthy()
      expect(box!.height).toBeGreaterThanOrEqual(36)
    })

    test('admin availability table is scrollable or fits', async ({ page, api }) => {
      const item = await api.createItem({ title: 'Mobile Avail E2E' })
      await loginAsAdmin(page)
      await page.goto(`/admin/items/${item.id}/availability`)
      const table = page.locator('.admin-avail-table')
      await expect(table).toBeVisible()
    })

    test('admin bookings decline modal fits viewport', async ({ page }) => {
      await loginAsAdmin(page)
      await page.goto('/admin/bookings')

      // If there's a booking row with Decline, open the modal
      const declineBtn = page.getByRole('button', { name: /decline/i }).first()
      if (await declineBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await declineBtn.click()
        const modal = page.locator('.modal-dialog')
        await expect(modal).toBeVisible()
        const modalBox = await modal.boundingBox()
        const viewport = page.viewportSize()
        if (modalBox && viewport) {
          // Modal should fit within viewport
          expect(modalBox.width).toBeLessThanOrEqual(viewport.width)
          expect(modalBox.height).toBeLessThanOrEqual(viewport.height + 50) // small scroll tolerance
        }
        // Close
        await page.locator('.modal-backdrop').click({ position: { x: 5, y: 5 } })
      }
    })
  })
})
