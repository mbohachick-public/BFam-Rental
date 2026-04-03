import { test as base, expect, type Page, type APIRequestContext } from '@playwright/test'

const API_BASE = 'http://localhost:8000'
const ADMIN_TOKEN = process.env.ADMIN_STUB_TOKEN ?? 'dev-admin-change-me'

/* ------------------------------------------------------------------ */
/*  Helpers – direct API calls for seeding / teardown                  */
/* ------------------------------------------------------------------ */

export async function adminApi(request: APIRequestContext) {
  const headers = { 'X-Admin-Token': ADMIN_TOKEN }

  async function createItem(overrides: Record<string, unknown> = {}) {
    const body = {
      title: `E2E Test Item ${Date.now()}`,
      description: 'Auto-created for E2E testing',
      category: 'e2e-test',
      cost_per_day: '50.00',
      minimum_day_rental: 1,
      deposit_amount: '100.00',
      user_requirements: 'None',
      towable: false,
      active: true,
      image_urls: [],
      ...overrides,
    }
    const res = await request.post(`${API_BASE}/admin/items`, {
      headers: { ...headers, 'Content-Type': 'application/json' },
      data: body,
    })
    expect(res.ok(), `createItem failed: ${res.status()}`).toBeTruthy()
    return res.json()
  }

  async function patchItem(itemId: string, patch: Record<string, unknown>) {
    const res = await request.patch(`${API_BASE}/admin/items/${itemId}`, {
      headers: { ...headers, 'Content-Type': 'application/json' },
      data: patch,
    })
    expect(res.ok(), `patchItem failed: ${res.status()}`).toBeTruthy()
    return res.json()
  }

  async function setDayStatuses(
    itemId: string,
    days: Array<{ day: string; status: string }>,
  ) {
    const res = await request.put(`${API_BASE}/admin/items/${itemId}/availability`, {
      headers: { ...headers, 'Content-Type': 'application/json' },
      data: { days },
    })
    expect(res.status()).toBe(204)
  }

  async function listItems() {
    const res = await request.get(`${API_BASE}/admin/items`, { headers })
    expect(res.ok()).toBeTruthy()
    return res.json() as Promise<Array<{ id: string; title: string; category: string }>>
  }

  async function listBookings() {
    const res = await request.get(`${API_BASE}/admin/booking-requests`, { headers })
    expect(res.ok()).toBeTruthy()
    return res.json() as Promise<Array<Record<string, unknown>>>
  }

  async function uploadImage(itemId: string, filename: string, mime: string, bytes: Buffer) {
    const res = await request.post(`${API_BASE}/admin/items/${itemId}/images`, {
      headers,
      multipart: { file: { name: filename, mimeType: mime, buffer: bytes } },
    })
    return res
  }

  async function deleteImage(itemId: string, imageId: string) {
    const res = await request.delete(`${API_BASE}/admin/items/${itemId}/images/${imageId}`, {
      headers,
    })
    return res
  }

  return {
    headers,
    createItem,
    patchItem,
    setDayStatuses,
    listItems,
    listBookings,
    uploadImage,
    deleteImage,
  }
}

/* ------------------------------------------------------------------ */
/*  Helper: log in as admin through the browser UI                     */
/* ------------------------------------------------------------------ */

export async function loginAsAdmin(page: Page) {
  await page.goto('/admin/login')
  await page.getByLabel('Admin token').fill(ADMIN_TOKEN)
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.waitForURL(/\/admin\/items/)
}

/* ------------------------------------------------------------------ */
/*  Helper: generate date strings relative to today                    */
/* ------------------------------------------------------------------ */

export function futureDate(daysFromNow: number): string {
  const d = new Date()
  d.setDate(d.getDate() + daysFromNow)
  return d.toISOString().slice(0, 10)
}

export function todayStr(): string {
  return new Date().toISOString().slice(0, 10)
}

/* ------------------------------------------------------------------ */
/*  Helper: 1x1 pixel test images                                     */
/* ------------------------------------------------------------------ */

export function tinyJpeg(): Buffer {
  return Buffer.from(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMCwsK' +
      'CwsLDBAQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQU' +
      'FBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAABAAEDASIAAhEB' +
      'AxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9' +
      'AQIDAAQRBRIHMQUGE0FRcRMiI4EUMpGhBxWxQiPBUtHhMxZi8CRygvElQzRTkqKyY3PCNUQnk6Oz' +
      'NhdUZHTD0uIIJoMJChgZhJRFRqS0VtNVKBry4/PE1OT0ZXWFlaW1xdXl9WZ2hpamtsbW5vYnN0dX' +
      'Z3eHl6e3x9fn9zhIWGh4iJiouMjY6PgpOUlZaXmJmam5ydnp+So6SlpqeoqaqrrK2ur6/9oADAMB' +
      'AAIRAxEAPwD9U6KKKACiiigD/9k=',
    'base64',
  )
}

export function tinyPng(): Buffer {
  return Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    'base64',
  )
}

/* ------------------------------------------------------------------ */
/*  Extended test fixture                                              */
/* ------------------------------------------------------------------ */

type Fixtures = {
  api: Awaited<ReturnType<typeof adminApi>>
}

export const test = base.extend<Fixtures>({
  api: async ({ request }, use) => {
    const api = await adminApi(request)
    await use(api)
  },
})

export { expect }
