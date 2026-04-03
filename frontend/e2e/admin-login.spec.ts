import { test, expect } from './fixtures'

const ADMIN_TOKEN = process.env.ADMIN_STUB_TOKEN ?? 'dev-admin-change-me'

test.describe('Admin login', () => {
  test('shows login form and rejects empty token', async ({ page }) => {
    await page.goto('/admin/login')
    await expect(page.getByRole('heading', { name: /admin/i })).toBeVisible()
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page.getByText(/enter the admin token/i)).toBeVisible()
  })

  test('successful login redirects to admin items', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByLabel('Admin token').fill(ADMIN_TOKEN)
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page).toHaveURL(/\/admin\/items/)
    await expect(page.getByRole('heading', { name: /items/i })).toBeVisible()
  })

  test('already-authenticated admin is redirected away from login', async ({ page }) => {
    // First log in
    await page.goto('/admin/login')
    await page.getByLabel('Admin token').fill(ADMIN_TOKEN)
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page).toHaveURL(/\/admin\/items/)

    // Navigate back to login
    await page.goto('/admin/login')
    // Should redirect to admin items since already logged in
    await expect(page).toHaveURL(/\/admin\/items/)
  })

  test('/admin redirects to /admin/items', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByLabel('Admin token').fill(ADMIN_TOKEN)
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page).toHaveURL(/\/admin\/items/)

    await page.goto('/admin')
    await expect(page).toHaveURL(/\/admin\/items/)
  })
})
