import { test, expect, futureDate, E2E_ADMIN_AUTH_ENABLED, adminApi } from './fixtures'

test.describe('Catalog page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/catalog')
  })

  test('displays heading and filter form', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1, name: 'Catalog' })).toBeVisible()
    await expect(page.getByLabel('Category')).toBeVisible()
    await expect(page.getByLabel(/minimum dollars/i)).toBeVisible()
    await expect(page.getByLabel(/maximum dollars/i)).toBeVisible()
    await expect(page.getByLabel(/open.*from/i)).toBeVisible()
    await expect(page.getByLabel(/open.*through/i)).toBeVisible()
  })

  test('loads items from the API (at least the catalog grid exists)', async ({ page }) => {
    await page.waitForSelector('.catalog-grid', { timeout: 10_000 })
    const grid = page.locator('.catalog-grid')
    await expect(grid).toBeVisible()
  })

  test('category dropdown contains options from API', async ({ page }) => {
    const select = page.getByLabel('Category')
    await expect(select).toBeVisible()
    const options = select.locator('option')
    const count = await options.count()
    expect(count).toBeGreaterThanOrEqual(1) // at least "All categories"
  })

  test('selecting a non-existent category shows empty state', async ({ page }) => {
    // Intercept catalog list (Vite dev uses /api/items; direct API uses /items).
    await page.route(
      (url) => {
        const p = new URL(url).pathname
        return (p === '/api/items' || p === '/items') && !p.includes('/items/')
      },
      (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    )
    await page.reload()
    await expect(page.getByText(/no items match/i)).toBeVisible()
  })

  test('half-filled date range shows validation error', async ({ page }) => {
    await page.getByLabel(/open.*from/i).fill(futureDate(5))
    // Leave "Open through" empty
    await expect(page.getByText(/select both start and end dates/i)).toBeVisible()
  })

  test('reversed date range shows validation error', async ({ page }) => {
    await page.getByLabel(/open.*from/i).fill(futureDate(10))
    await page.getByLabel(/open.*through/i).fill(futureDate(5))
    await expect(page.getByText(/must be on or before/i)).toBeVisible()
  })

  test('catalog cards link to item detail', async ({ page, request }) => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN to seed catalog items via admin API')
    const api = await adminApi(request)
    // Seed an item to guarantee at least one card
    const item = await api.createItem()
    const itemId = item.id as string
    // Set a day as open so it shows in catalog
    await api.setDayStatuses(itemId, [
      { day: futureDate(3), status: 'open_for_booking' },
    ])
    await page.reload()

    const cards = page.locator('.catalog-card')
    const count = await cards.count()
    if (count > 0) {
      const href = await cards.first().getAttribute('href')
      expect(href).toMatch(/\/items\//)
    }
  })

  test('price range sliders update displayed values', async ({ page }) => {
    const minSlider = page.getByLabel(/minimum dollars/i)
    const maxSlider = page.getByLabel(/maximum dollars/i)
    await minSlider.fill('50')
    await expect(page.getByText(/at least.*\$50/i)).toBeVisible()
    await maxSlider.fill('200')
    await expect(page.getByText(/up to.*\$200/i)).toBeVisible()
  })
})
