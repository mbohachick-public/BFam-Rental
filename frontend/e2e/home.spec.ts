import { test, expect } from './fixtures'

test.describe('Home page', () => {
  test('renders hero with heading and CTA link to catalog', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: /rent/i })).toBeVisible()
    const cta = page.getByRole('link', { name: /browse catalog/i })
    await expect(cta).toBeVisible()
    await cta.click()
    await expect(page).toHaveURL(/\/catalog/)
  })

  test('shows three feature cards', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Clear pricing')).toBeVisible()
    await expect(page.getByText('Live calendar')).toBeVisible()
    await expect(page.getByText('Request online')).toBeVisible()
  })

  test('unknown routes redirect to home', async ({ page }) => {
    await page.goto('/this-does-not-exist')
    await expect(page).toHaveURL('/')
  })
})
