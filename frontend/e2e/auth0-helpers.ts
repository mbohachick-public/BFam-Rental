import path from 'node:path'
import { fileURLToPath } from 'node:url'

import dotenv from 'dotenv'
import { expect, type Page } from '@playwright/test'

/* Playwright workers may not inherit env from playwright.config.ts; load .env here too. */
const _e2eDir = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({
  path: path.join(_e2eDir, '..', '.env'),
  override: true,
})

/** Real Auth0 login e2e runs only when these are set (plus VITE_AUTH0_* in .env for the SPA). */
export function auth0RealLoginConfigured(): boolean {
  return Boolean(
    process.env.E2E_AUTH0_EMAIL?.trim() &&
      process.env.E2E_AUTH0_PASSWORD?.trim() &&
      process.env.VITE_AUTH0_DOMAIN?.trim() &&
      process.env.VITE_AUTH0_CLIENT_ID?.trim(),
  )
}

export function toUrl(u: URL | string): URL {
  return typeof u === 'string' ? new URL(u) : u
}

/** True when the SPA is on the same dev machine the test uses (localhost / 127.0.0.1 / ::1). */
export function isAppLoopbackHost(hostname: string, appHostname: string): boolean {
  const loop = new Set(['localhost', '127.0.0.1', '[::1]', '::1'])
  return hostname === appHostname || (loop.has(hostname) && loop.has(appHostname))
}

/**
 * Poll until `page.url()` is on the app loopback host (OAuth callback or post-exchange SPA).
 * Throws if Auth0 redirects with `error` / `error_description` query params.
 */
export async function waitUntilOnAppOrigin(
  page: Page,
  appHostname: string,
  timeoutMs: number,
): Promise<void> {
  await expect
    .poll(
      () => {
        try {
          const u = new URL(page.url())
          if (!isAppLoopbackHost(u.hostname, appHostname)) return false
          const err = u.searchParams.get('error')
          if (err) {
            throw new Error(
              `OAuth callback failed: ${err} — ${u.searchParams.get('error_description') ?? ''} (${u.href})`,
            )
          }
          return true
        } catch (e) {
          if (e instanceof Error && e.message.startsWith('OAuth callback')) throw e
          return false
        }
      },
      { timeout: timeoutMs, intervals: [100, 250, 500, 1000] },
    )
    .toBe(true)
}

/** Auth0 SPA SDK cache keys in localStorage (substring match). */
export async function hasAuth0SpaCache(page: Page): Promise<boolean> {
  return page.evaluate(() =>
    Object.keys(window.localStorage).some(
      (k) => k.includes('@@auth0spajs@@') || k.includes('auth0spajs'),
    ),
  )
}

/** Visible password field on Auth0 Universal Login (re-resolve after each step — DOM swaps). */
function auth0PasswordInput(page: Page) {
  return page
    .getByRole('textbox', { name: /^password$/i })
    .or(page.getByLabel(/^password$/i))
    .or(page.locator('input[type="password"][autocomplete="current-password"]'))
    .or(page.locator('input[type="password"][name="password"]'))
    .or(page.locator('input[type="password"][id="password"]'))
    .or(page.locator('input[type="password"]'))
    .first()
}

async function fillAuth0Password(page: Page, password: string): Promise<void> {
  const passwordInput = auth0PasswordInput(page)
  await passwordInput.waitFor({ state: 'visible', timeout: 25_000 })
  await passwordInput.scrollIntoViewIfNeeded()
  await passwordInput.click({ timeout: 5000 })
  await passwordInput.clear()
  /* Some Auth0 builds miss `input` events with instant fill — keystrokes match real typing. */
  await page.keyboard.type(password, { delay: 25 })
  const got = await passwordInput.inputValue()
  if (got.length !== password.length) {
    await passwordInput.fill(password, { force: true })
  }
  const final = await passwordInput.inputValue()
  if (final.length !== password.length) {
    throw new Error(
      `Password field did not accept full input (expected ${password.length} chars, got ${final.length}). Check Auth0 Universal Login selectors / overlays.`,
    )
  }
}

/**
 * Complete Auth0 Universal Login (username-password DB) on the hosted page.
 * Then wait until the browser is back on the app origin (handles consent + slow redirects).
 */
export async function completeAuth0UniversalLogin(
  page: Page,
  email: string,
  password: string,
  appHostname: string,
): Promise<void> {
  const emailInput = page
    .getByLabel(/^email( address)?$/i)
    .or(page.locator('input[type="email"]'))
    .or(page.locator('input[name="username"]'))
    .or(page.locator('input#username'))
    .first()

  await emailInput.waitFor({ state: 'visible', timeout: 45_000 })
  await emailInput.click()
  await emailInput.clear()
  await emailInput.fill(email)

  const passwordMaybeVisible = await auth0PasswordInput(page).isVisible().catch(() => false)
  if (!passwordMaybeVisible) {
    const next = page.getByRole('button', { name: /^(continue|next)$/i }).first()
    await next.waitFor({ state: 'visible', timeout: 15_000 })
    await next.click()
  }

  await fillAuth0Password(page, password)

  const primary = page.locator('button[data-action-button-primary="true"]')
  if (await primary.isVisible().catch(() => false)) {
    await primary.click()
  } else {
    await page.getByRole('button', { name: /^(log in|continue|verify)$/i }).first().click()
  }

  const accept = page.getByRole('button', { name: /^(accept|authorize|allow)$/i })
  try {
    await accept.waitFor({ state: 'visible', timeout: 8000 })
    await accept.click()
  } catch {
    /* no consent step */
  }

  await waitUntilOnAppOrigin(page, appHostname, 120_000)
}
