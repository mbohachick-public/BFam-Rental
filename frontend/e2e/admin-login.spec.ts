import { test, expect, E2E_ADMIN_AUTH_ENABLED } from './fixtures'

test.describe('Admin login', () => {
  test.beforeAll(() => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN (and VITE_E2E_AUTH0_ACCESS_TOKEN for the dev server)')
  })

  test('continue to admin redirects to admin items', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByRole('button', { name: /continue to admin/i }).click()
    await expect(page).toHaveURL(/\/admin\/items/)
    await expect(page.getByRole('heading', { name: /items/i })).toBeVisible()
  })

  test('returning to login redirects when admin session is active', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByRole('button', { name: /continue to admin/i }).click()
    await expect(page).toHaveURL(/\/admin\/items/)

    await page.goto('/admin/login')
    await expect(page).toHaveURL(/\/admin\/items/)
  })

  test('/admin redirects to /admin/items', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByRole('button', { name: /continue to admin/i }).click()
    await expect(page).toHaveURL(/\/admin\/items/)

    await page.goto('/admin')
    await expect(page).toHaveURL(/\/admin\/items/)
  })
})
