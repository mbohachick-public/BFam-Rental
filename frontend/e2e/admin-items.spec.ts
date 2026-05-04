import { test, expect, loginAsAdmin, E2E_ADMIN_AUTH_ENABLED } from './fixtures'

test.describe('Admin items list and CRUD', () => {
  test.beforeAll((_worker, testInfo) => {
    testInfo.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN (and backend Auth0 + admin rules)')
  })

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('items list page renders with heading and add button', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /items/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /add item/i })).toBeVisible()
  })

  test('create a new item and see it in the list', async ({ page }) => {
    await page.getByRole('link', { name: /add item/i }).click()
    await expect(page).toHaveURL(/\/admin\/items\/new/)

    const title = `E2E Admin Item ${Date.now()}`
    await page.getByLabel('Title').fill(title)
    await page.getByLabel('Category').fill('e2e-admin')
    await page.getByLabel('Cost per day').fill('75')
    await page.getByLabel('Minimum days').fill('2')
    await page.getByLabel('Deposit').fill('200')

    await page.getByRole('button', { name: /save/i }).click()

    // Should redirect to edit page after create (with id in URL)
    await expect(page).toHaveURL(/\/admin\/items\/[a-f0-9-]+\/edit/)
  })

  test('edit an existing item', async ({ page, api }) => {
    const item = await api.createItem({ title: 'Edit Me E2E' })
    const itemId = item.id as string

    await page.goto(`/admin/items/${itemId}/edit`)
    await expect(page.getByLabel('Title')).toHaveValue('Edit Me E2E')

    await page.getByLabel('Title').fill('Edited By E2E')
    await page.getByRole('button', { name: /save/i }).click()
    await expect(page).toHaveURL(/\/admin\/items$/)
  })

  test('active toggle: inactive item shows badge in list', async ({ page, api }) => {
    const item = await api.createItem({ title: 'Inactive E2E', active: true })
    const itemId = item.id as string

    // Mark inactive via API
    await api.patchItem(itemId, { active: false })

    await page.goto('/admin/items')
    const row = page.locator('.admin-table-row', { hasText: 'Inactive E2E' })
    await expect(row).toBeVisible()
    await expect(row).toHaveClass(/admin-table-row-inactive/)
    await expect(row.locator('.admin-badge-inactive')).toHaveText(/inactive/i)
  })

  test('active toggle: inactive item hidden from public catalog', async ({ page, api }) => {
    const item = await api.createItem({ title: 'Hidden E2E', active: false })
    const itemId = item.id as string

    // Public catalog should not show this item
    await page.goto('/catalog')
    await page.waitForTimeout(1000)
    const card = page.locator('.catalog-card', { hasText: 'Hidden E2E' })
    await expect(card).toHaveCount(0)

    // Public detail should 404
    await page.goto(`/items/${itemId}`)
    await expect(page.getByText(/not found/i)).toBeVisible()
  })

  test('edit form has active/visible checkbox', async ({ page, api }) => {
    const item = await api.createItem()
    await page.goto(`/admin/items/${item.id}/edit`)
    const checkbox = page.getByLabel(/visible in catalog/i)
    await expect(checkbox).toBeVisible()
    await expect(checkbox).toBeChecked()

    // Uncheck and save
    await checkbox.uncheck()
    await expect(checkbox).not.toBeChecked()
  })

  test('edit form has towable checkbox', async ({ page, api }) => {
    const item = await api.createItem({ towable: true })
    await page.goto(`/admin/items/${item.id}/edit`)
    const checkbox = page.getByLabel(/towable/i)
    await expect(checkbox).toBeVisible()
    await expect(checkbox).toBeChecked()
  })

  test('items list has edit and calendar links', async ({ page, api }) => {
    await api.createItem({ title: 'Links E2E' })
    await page.goto('/admin/items')

    const row = page.locator('.admin-table-row', { hasText: 'Links E2E' })
    await expect(row.getByRole('link', { name: /edit/i })).toBeVisible()
    await expect(row.getByRole('link', { name: /calendar/i })).toBeVisible()
  })
})
