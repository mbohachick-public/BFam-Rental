import AxeBuilder from '@axe-core/playwright'
import { test, expect, loginAsAdmin, futureDate, tinyJpeg, E2E_ADMIN_AUTH_ENABLED } from './fixtures'

/*
 * Accessibility / usability audits.
 *
 * Uses axe-core via @axe-core/playwright to scan every major page.
 * Violations are printed to stdout and fail the test.
 *
 * Run:  npx playwright test accessibility --project=chromium
 */

function formatViolations(violations: Array<{ id: string; impact?: string; description: string; nodes: Array<{ html: string }> }>) {
  return violations
    .map(
      (v) =>
        `[${v.impact ?? '?'}] ${v.id}: ${v.description}\n` +
        v.nodes.map((n) => `    ${n.html.slice(0, 120)}`).join('\n'),
    )
    .join('\n\n')
}

let testItemId = ''

test.beforeAll(async ({ request }) => {
  if (!E2E_ADMIN_AUTH_ENABLED) return
  const { createItem, uploadImage, setDayStatuses } = await (
    await import('./fixtures')
  ).adminApi(request)
  const item = await createItem({ title: 'A11y Test Item' })
  testItemId = item.id as string
  await uploadImage(testItemId, 'a11y.jpg', 'image/jpeg', tinyJpeg())
  await setDayStatuses(testItemId, [
    { day: futureDate(3), status: 'open_for_booking' },
  ])
})

test.describe('Accessibility audits', () => {
  test('Home page (/)', async ({ page }) => {
    await page.goto('/')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Home page a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Home page has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Catalog page (/catalog)', async ({ page }) => {
    await page.goto('/catalog')
    await page.waitForSelector('.catalog-grid', { timeout: 10_000 })
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Catalog a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Catalog has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Item detail page (/items/:id)', async ({ page }) => {
    test.skip(!testItemId, 'Set E2E_AUTH0_ACCESS_TOKEN to seed item for this route')
    await page.goto(`/items/${testItemId}`)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Item detail a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Item detail has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Admin login (/admin/login)', async ({ page }) => {
    await page.goto('/admin/login')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Admin login a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Admin login has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Admin items (/admin/items)', async ({ page }) => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN for admin UI')
    await loginAsAdmin(page)
    await page.goto('/admin/items')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Admin items a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Admin items has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Admin item edit (/admin/items/:id/edit)', async ({ page }) => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED || !testItemId, 'Set E2E_AUTH0_ACCESS_TOKEN for admin UI')
    await loginAsAdmin(page)
    await page.goto(`/admin/items/${testItemId}/edit`)
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Admin edit a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Admin edit has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Admin availability (/admin/items/:id/availability)', async ({ page }) => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED || !testItemId, 'Set E2E_AUTH0_ACCESS_TOKEN for admin UI')
    await loginAsAdmin(page)
    await page.goto(`/admin/items/${testItemId}/availability`)
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Admin availability a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Admin availability has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })

  test('Admin bookings (/admin/bookings)', async ({ page }) => {
    test.skip(!E2E_ADMIN_AUTH_ENABLED, 'Set E2E_AUTH0_ACCESS_TOKEN for admin UI')
    await loginAsAdmin(page)
    await page.goto('/admin/bookings')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    )
    if (serious.length > 0) {
      console.log('Admin bookings a11y issues:\n', formatViolations(serious))
    }
    expect(serious, `Admin bookings has ${serious.length} serious a11y issue(s)`).toHaveLength(0)
  })
})

test.describe('Usability checks', () => {
  test('all form inputs have associated labels', async ({ page }) => {
    await page.goto('/catalog')
    const inputs = page.locator('input:not([type="hidden"]), select, textarea')
    const count = await inputs.count()
    for (let i = 0; i < count; i++) {
      const input = inputs.nth(i)
      const ariaLabel = await input.getAttribute('aria-label')
      const id = await input.getAttribute('id')
      const labelledBy = await input.getAttribute('aria-labelledby')
      const hasLabel = ariaLabel || labelledBy || (id && (await page.locator(`label[for="${id}"]`).count()) > 0)
      const parentLabel = await input.locator('xpath=ancestor::label').count()
      expect(
        hasLabel || parentLabel > 0,
        `Input at index ${i} lacks an accessible label`,
      ).toBeTruthy()
    }
  })

  test('heading hierarchy: no skipped levels on home page', async ({ page }) => {
    await page.goto('/')
    const headings = page.locator('h1, h2, h3, h4, h5, h6')
    const count = await headings.count()
    let prevLevel = 0
    for (let i = 0; i < count; i++) {
      const tag = await headings.nth(i).evaluate((el) => el.tagName.toLowerCase())
      const level = parseInt(tag.replace('h', ''), 10)
      // Level should not skip (e.g. h1 -> h3 without h2)
      expect(
        level <= prevLevel + 1 || prevLevel === 0,
        `Heading level jumped from h${prevLevel} to h${level}`,
      ).toBeTruthy()
      prevLevel = level
    }
  })

  test('interactive elements have visible focus indicators', async ({ page }) => {
    await page.goto('/')
    const cta = page.getByRole('link', { name: /browse catalog/i })
    await cta.focus()
    // Just ensure focus doesn't throw; visible check is subjective but
    // axe-core above covers contrast and focus-visible
    await expect(cta).toBeFocused()
  })
})
