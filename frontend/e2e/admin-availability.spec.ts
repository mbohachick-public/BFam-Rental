import { test, expect, loginAsAdmin } from './fixtures'

test.describe('Admin availability calendar', () => {
  let itemId: string
  let itemTitle: string

  test.beforeAll(async ({ request }) => {
    const { createItem } = await (await import('./fixtures')).adminApi(request)
    const item = await createItem({ title: 'Avail E2E' })
    itemId = item.id as string
    itemTitle = item.title as string
  })

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('calendar page renders with item title', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/availability`)
    await expect(page.getByRole('heading', { name: new RegExp(itemTitle) })).toBeVisible()
  })

  test('calendar has month navigation buttons', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/availability`)
    await expect(page.getByRole('button', { name: /previous month/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /next month/i })).toBeVisible()
  })

  test('can navigate to next and previous month', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/availability`)
    await page.getByRole('button', { name: /next month/i }).click()
    // Should remain on availability page
    await expect(page).toHaveURL(new RegExp(`/admin/items/${itemId}/availability`))
    await page.getByRole('button', { name: /previous month/i }).click()
    await expect(page).toHaveURL(new RegExp(`/admin/items/${itemId}/availability`))
  })

  test('calendar table shows date rows with status dropdowns', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/availability`)
    const table = page.locator('.admin-avail-table')
    await expect(table).toBeVisible()
    // Should have at least 28 rows (shortest month)
    const rows = table.locator('tbody tr')
    const count = await rows.count()
    expect(count).toBeGreaterThanOrEqual(28)
  })

  test('save button persists changes', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/availability`)
    const saveBtn = page.getByRole('button', { name: /save/i })
    await expect(saveBtn).toBeVisible()
    await saveBtn.click()
    await expect(page.getByText(/saved/i)).toBeVisible()
  })

  test('inactive item shows banner on calendar page', async ({ page, api }) => {
    const item = await api.createItem({ title: 'Inactive Avail E2E', active: false })
    await page.goto(`/admin/items/${item.id}/availability`)
    await expect(page.getByText(/inactive/i)).toBeVisible()
  })

  test('breadcrumb links back to items list', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/availability`)
    const crumb = page.locator('.breadcrumb').getByRole('link', { name: /items/i })
    await crumb.click()
    await expect(page).toHaveURL(/\/admin\/items$/)
  })
})
