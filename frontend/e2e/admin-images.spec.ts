import { test, expect, loginAsAdmin, tinyJpeg, tinyPng } from './fixtures'

test.describe('Admin item image uploads', () => {
  let itemId: string

  test.beforeAll(async ({ request }) => {
    const { createItem } = await (await import('./fixtures')).adminApi(request)
    const item = await createItem({ title: 'Image Test E2E' })
    itemId = item.id as string
  })

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('upload an image and see it in the edit form', async ({ page }) => {
    await page.goto(`/admin/items/${itemId}/edit`)
    await expect(page.getByText(/photos/i)).toBeVisible()

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test.jpg',
      mimeType: 'image/jpeg',
      buffer: tinyJpeg(),
    })

    // Wait for the image to appear in the grid
    await expect(page.locator('.admin-item-images img').first()).toBeVisible({ timeout: 10_000 })
  })

  test('remove an image via remove button', async ({ page, api }) => {
    // Ensure at least one image exists
    const up = await api.uploadImage(itemId, 'remove-me.png', 'image/png', tinyPng())
    expect(up.ok(), `upload failed: ${up.status()} ${await up.text()}`).toBeTruthy()

    await page.goto(`/admin/items/${itemId}/edit`)
    const images = page.locator('.admin-item-images li')
    await expect(images.first()).toBeVisible({ timeout: 15_000 })
    const countBefore = await images.count()
    expect(countBefore).toBeGreaterThanOrEqual(1)

    await images.first().getByRole('button', { name: /remove/i }).click()
    // After removal the count should decrease
    await expect(page.locator('.admin-item-images li')).toHaveCount(countBefore - 1)
  })

  test('max 10 images enforcement via API', async ({ api }) => {
    // Create a fresh item and upload 10 images
    const item = await api.createItem({ title: 'Max Images E2E' })
    const id = item.id as string

    for (let i = 0; i < 10; i++) {
      const res = await api.uploadImage(id, `img${i}.jpg`, 'image/jpeg', tinyJpeg())
      expect(res.ok(), `upload ${i} failed`).toBeTruthy()
    }

    // 11th should fail
    const res = await api.uploadImage(id, 'img10.jpg', 'image/jpeg', tinyJpeg())
    expect(res.status()).toBe(400)
    const body = await res.json()
    expect(body.detail).toMatch(/at most 10/i)
  })

  test('slots remaining text updates', async ({ page, api }) => {
    const item = await api.createItem({ title: 'Slots E2E' })
    await page.goto(`/admin/items/${item.id}/edit`)
    // Fresh item should show "10 slots left"
    await expect(page.getByText(/10 slots left/i)).toBeVisible()
  })

  test('new item shows save-first message', async ({ page }) => {
    await page.goto('/admin/items/new')
    await expect(page.getByText(/save the item once/i)).toBeVisible()
  })
})
