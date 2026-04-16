import path from 'node:path'
import { fileURLToPath } from 'node:url'

import dotenv from 'dotenv'
import { defineConfig, devices } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
/* Load frontend/.env so VITE_* and E2E_* are visible to tests and inherited by webServer. */
dotenv.config({ path: path.join(__dirname, '.env'), override: true })

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'html',
  timeout: 30_000,

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  // WebKit (Safari) is not installable on macOS 12 — use Chromium + iPhone emulation instead.
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'mobile-ios',
      use: {
        ...devices['iPhone 14'],
        browserName: 'chromium',
      },
    },
  ],

  webServer: [
    {
      command: 'cd ../backend && .venv/bin/python -m uvicorn app.main:app --port 8000',
      port: 8000,
      reuseExistingServer: true,
      timeout: 15_000,
      env: { ...process.env },
    },
    {
      command: 'npm run dev',
      port: 5173,
      reuseExistingServer: true,
      timeout: 15_000,
      env: {
        ...process.env,
        /* Same JWT as E2E_AUTH0_ACCESS_TOKEN — dev-only admin UI shim (see frontend/src/components/Auth0Root.tsx). */
        VITE_E2E_AUTH0_ACCESS_TOKEN: process.env.E2E_AUTH0_ACCESS_TOKEN ?? '',
      },
    },
  ],
})
