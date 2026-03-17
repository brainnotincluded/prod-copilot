import { test, expect } from '@playwright/test'

test.describe('Scenarios Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set mock auth
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'test-token')
      localStorage.setItem('auth_user', JSON.stringify({ id: 1, email: 'test@test.com', name: 'Test', role: 'admin' }))
    })
  })

  test('displays scenarios page', async ({ page }) => {
    await page.goto('/scenarios')
    await expect(page.locator('text=Scenarios').first()).toBeVisible({ timeout: 10000 })
  })

  test('shows empty state when no scenarios', async ({ page }) => {
    // Mock empty scenarios response
    await page.route('**/api/v1/scenarios*', route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    })
    await page.goto('/scenarios')
    await expect(page.locator('text=No scenarios yet').first()).toBeVisible({ timeout: 10000 })
  })

  test('displays scenario list with status badges', async ({ page }) => {
    await page.route('**/api/v1/scenarios*', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, correlation_id: 'abc', query: 'Find premium users', status: 'completed', graph_nodes: [], graph_edges: [], summary: {}, created_at: '2024-01-15T10:00:00Z', finished_at: '2024-01-15T10:01:00Z' },
          { id: 2, correlation_id: 'def', query: 'Create audience', status: 'error', graph_nodes: [], graph_edges: [], summary: {}, created_at: '2024-01-15T11:00:00Z', finished_at: null },
        ]),
      })
    })
    await page.goto('/scenarios')
    await expect(page.locator('text=Find premium users')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=Create audience')).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'test-token')
      localStorage.setItem('auth_user', JSON.stringify({ id: 1, email: 'test@test.com', name: 'Test', role: 'admin' }))
    })
  })

  test('displays dashboard with stats', async ({ page }) => {
    await page.route('**/api/v1/endpoints/stats', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total: 57, by_method: { GET: 30, POST: 15, PUT: 5, DELETE: 7 }, by_source: { 'Marketing API': 57 } }),
      })
    })
    await page.route('**/api/v1/swagger/list', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 1, name: 'Marketing API', endpoint_count: 57, created_at: '2024-01-15T10:00:00Z' }]),
      })
    })
    await page.route('**/api/v1/endpoints/list*', route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    })
    await page.goto('/dashboard')
    await expect(page.locator('text=57')).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'test-token')
      localStorage.setItem('auth_user', JSON.stringify({ id: 1, email: 'test@test.com', name: 'Test', role: 'admin' }))
    })
  })

  test('sidebar shows all navigation items on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/chat')
    await expect(page.locator('.sidebar .nav-item')).toHaveCount(6) // chat, history, sources, maps, scenarios, dashboard
  })

  test('navigates to scenarios page', async ({ page }) => {
    await page.goto('/chat')
    await page.click('a[href="/scenarios"]')
    await expect(page).toHaveURL('/scenarios')
  })

  test('navigates to dashboard page', async ({ page }) => {
    await page.goto('/chat')
    await page.click('a[href="/dashboard"]')
    await expect(page).toHaveURL('/dashboard')
  })
})
