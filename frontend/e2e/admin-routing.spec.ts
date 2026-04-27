import { test, expect, E2E_ADMIN_AUTH_ENABLED, loginAsAdmin } from './fixtures'

test.describe('Admin routing', () => {
  test.beforeAll(() => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN (and VITE_E2E_AUTH0_ACCESS_TOKEN for the dev server)')
  })

  test('admin items loads for an admin session', async ({ page }) => {
    await loginAsAdmin(page)
    await expect(page.getByRole('heading', { name: /items/i })).toBeVisible()
  })

  test('legacy /admin/login redirects to /admin/items', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/admin/login')
    await expect(page).toHaveURL(/\/admin\/items/)
  })

  test('/admin redirects to /admin/items', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/admin\/items/)
  })
})
