/**
 * Real Auth0 Authorization Code + PKCE flow (browser) and silent access token for API calls.
 *
 * Requires frontend/.env: VITE_AUTH0_DOMAIN, VITE_AUTH0_CLIENT_ID, VITE_AUTH0_AUDIENCE (match API),
 * plus E2E_AUTH0_EMAIL / E2E_AUTH0_PASSWORD for a Database user without MFA. Callback / logout /
 * Web Origins must include the Playwright base URL (e.g. http://localhost:5173).
 */
import { test, expect } from '@playwright/test'

import {
  auth0RealLoginConfigured,
  completeAuth0UniversalLogin,
  hasAuth0SpaCache,
  isAppLoopbackHost,
  toUrl,
} from './auth0-helpers'

const base = () => {
  const u = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'
  return u.replace(/\/$/, '')
}

test.describe('Auth0 real login (optional)', () => {
  test.skip(
    !auth0RealLoginConfigured(),
    'Set E2E_AUTH0_EMAIL, E2E_AUTH0_PASSWORD, and VITE_AUTH0_DOMAIN + VITE_AUTH0_CLIENT_ID in frontend/.env',
  )

  test.beforeEach(({ isMobile }) => {
    test.skip(isMobile, 'Auth0 hosted UI: desktop Chromium only (skip emulated mobile projects)')
  })

  test.describe.configure({ mode: 'serial' })
  test.setTimeout(180_000)

  test('Universal Login → callback stores SPA session and API sends Bearer JWT', async ({
    page,
  }) => {
    const email = process.env.E2E_AUTH0_EMAIL!.trim()
    const password = process.env.E2E_AUTH0_PASSWORD!

    await page.goto(`${base()}/`)
    await expect(page.getByRole('button', { name: /^sign in$/i })).toBeVisible({ timeout: 20_000 })

    await page.getByRole('button', { name: /^sign in$/i }).click()

    const appUrl = new URL(base())
    const originHost = appUrl.hostname
    await page.waitForURL(
      (u) => {
        const h = toUrl(u).hostname
        return !isAppLoopbackHost(h, originHost)
      },
      { timeout: 45_000, waitUntil: 'commit' },
    )

    await completeAuth0UniversalLogin(page, email, password, originHost)

    await expect(page.getByRole('button', { name: /^sign out$/i })).toBeVisible({ timeout: 60_000 })
    expect(await hasAuth0SpaCache(page)).toBe(true)

    const mineRequest = page.waitForRequest(
      (req) =>
        req.url().includes('/api/booking-requests/mine') &&
        Boolean(req.headers()['authorization']?.startsWith('Bearer ')),
      { timeout: 45_000 },
    )
    await page.goto(`${base()}/my-rentals`)
    const authorized = await mineRequest
    const authz = authorized.headers()['authorization']
    expect(authz).toMatch(/^Bearer ey/)

    await page.getByRole('button', { name: /^sign out$/i }).click()
    await expect(page.getByRole('button', { name: /^sign in$/i })).toBeVisible({ timeout: 25_000 })
  })
})
