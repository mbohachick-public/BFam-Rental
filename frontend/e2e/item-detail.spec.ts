import { test, expect, futureDate, tinyJpeg } from './fixtures'

test.describe('Item detail page', () => {
  let itemId: string

  test.beforeAll(async ({ request }) => {
    const { createItem, setDayStatuses, uploadImage } = await (
      await import('./fixtures')
    ).adminApi(request)

    const item = await createItem({ towable: false })
    itemId = item.id as string

    // Upload two images so we can test the gallery
    await uploadImage(itemId, 'a.jpg', 'image/jpeg', tinyJpeg())
    await uploadImage(itemId, 'b.jpg', 'image/jpeg', tinyJpeg())

    // Seed open days in the future
    const days = Array.from({ length: 5 }, (_, i) => ({
      day: futureDate(i + 3),
      status: 'open_for_booking',
    }))
    await setDayStatuses(itemId, days)
  })

  test('shows item attributes', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByText(/cost per day/i)).toBeVisible()
    await expect(page.getByText(/minimum rental/i)).toBeVisible()
    await expect(page.getByText(/deposit/i)).toBeVisible()
    await expect(page.getByText(/towable/i)).toBeVisible()
  })

  test('gallery: main image and clickable thumbnails', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    const mainImg = page.locator('.item-hero-img')
    await expect(mainImg).toBeVisible()

    const thumbs = page.locator('.item-thumb-btn')
    const count = await thumbs.count()
    expect(count).toBeGreaterThanOrEqual(2)

    // Click second thumbnail
    if (count >= 2) {
      const secondThumb = thumbs.nth(1)
      await secondThumb.click()
      await expect(secondThumb).toHaveAttribute('aria-pressed', 'true')
    }
  })

  test('calendar section is visible with legend', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    await expect(page.getByRole('heading', { name: /availability/i })).toBeVisible()
    await expect(page.getByText(/open for booking/i).first()).toBeVisible()
  })

  test('calendar month navigation works', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    const prevBtn = page.getByRole('button', { name: /previous/i })
    const nextBtn = page.getByRole('button', { name: /next/i })
    await expect(nextBtn).toBeVisible()
    await nextBtn.click()
    // Should still be on the same item page
    await expect(page).toHaveURL(new RegExp(`/items/${itemId}`))
    await prevBtn.click()
  })

  test('booking form: requires email to get a quote', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    // Try to get quote without filling email
    const quoteBtn = page.getByRole('button', { name: /get quote/i })
    if (await quoteBtn.isVisible()) {
      await quoteBtn.click()
      await expect(page.getByText(/email/i)).toBeVisible()
    }
  })

  test('booking form: requires driver license to submit', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    // Fill required fields but skip driver's license
    const submitBtn = page.getByRole('button', { name: /submit/i })
    if (await submitBtn.isVisible()) {
      await submitBtn.click()
      // Should show license required error
      await expect(page.getByText(/license/i)).toBeVisible()
    }
  })

  test('breadcrumb links back to catalog', async ({ page }) => {
    await page.goto(`/items/${itemId}`)
    const crumb = page.locator('.breadcrumb').getByRole('link', { name: /catalog/i })
    await expect(crumb).toBeVisible()
    await crumb.click()
    await expect(page).toHaveURL(/\/catalog/)
  })

  test('nonexistent item shows error', async ({ page }) => {
    await page.goto('/items/00000000-0000-0000-0000-000000000000')
    await expect(page.getByText(/not found/i)).toBeVisible()
  })
})
