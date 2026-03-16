/**
 * Visual Regression Tests with Mock Data
 * 
 * These tests use mock data to ensure consistent screenshots
 * Run with: npx playwright test visual.spec.ts
 */

import { test, expect } from '@playwright/test'

// Helper to enable mocks
const gotoWithMocks = async (page, path: string) => {
  await page.goto(`${path}?useMocks`)
  // Wait for mock data to load
  await page.waitForTimeout(500)
}

test.describe('Visual Regression - Desktop (1440x900)', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
  })

  test('Chat page', async ({ page }) => {
    await gotoWithMocks(page, '/chat')
    await page.waitForSelector('.chat-input-wrapper')
    await expect(page).toHaveScreenshot('chat-desktop.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
  })

  test('API Sources page with connected sources', async ({ page }) => {
    await gotoWithMocks(page, '/swagger')
    // Wait for sources to render
    await page.waitForSelector('.list-items')
    await expect(page).toHaveScreenshot('swagger-desktop.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
  })

  test('API Maps page with mock endpoints', async ({ page }) => {
    await gotoWithMocks(page, '/endpoints')
    // Wait for VueFlow to initialize
    await page.waitForSelector('.vue-flow__nodes')
    await page.waitForTimeout(1000) // Let graph settle
    await expect(page).toHaveScreenshot('api-maps-desktop.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
  })
})

test.describe('Visual Regression - Mobile (390x844)', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
  })

  test('Chat page', async ({ page }) => {
    await gotoWithMocks(page, '/chat')
    await page.waitForSelector('.chat-input-wrapper')
    await expect(page).toHaveScreenshot('chat-mobile.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
  })

  test('API Sources page - no overlap', async ({ page }) => {
    await gotoWithMocks(page, '/swagger')
    // Wait for sources to render
    await page.waitForSelector('.list-items')
    
    // Check that section header doesn't overlap with pull-to-refresh
    const sectionHeader = await page.locator('.section-header').first()
    await expect(sectionHeader).toBeVisible()
    
    // Take screenshot to verify no overlap
    await expect(page).toHaveScreenshot('swagger-mobile.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
    
    // Verify the title and button don't overlap
    const title = await page.locator('.section-title').first()
    const refreshBtn = await page.locator('.refresh-btn').first()
    
    const titleBox = await title.boundingBox()
    const btnBox = await refreshBtn.boundingBox()
    
    // Title and button should not overlap
    if (titleBox && btnBox) {
      const overlap = !(titleBox.x + titleBox.width < btnBox.x || 
                        btnBox.x + btnBox.width < titleBox.x)
      // On mobile they might be on same row, but should have gap
      expect(titleBox.x + titleBox.width).toBeLessThanOrEqual(btnBox.x + 5) // Allow small tolerance
    }
  })

  test('API Maps page', async ({ page }) => {
    await gotoWithMocks(page, '/endpoints')
    // Wait for VueFlow
    await page.waitForSelector('.vue-flow__nodes')
    await page.waitForTimeout(1000)
    await expect(page).toHaveScreenshot('api-maps-mobile.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
  })

  test('Bottom navigation visible', async ({ page }) => {
    await gotoWithMocks(page, '/chat')
    const bottomNav = page.locator('.bottom-nav')
    await expect(bottomNav).toBeVisible()
    
    // Verify 3 nav items (Chat, API Sources, API Maps) - no Dashboard
    const navItems = bottomNav.locator('.nav-item')
    await expect(navItems).toHaveCount(3)
    
    // Take screenshot of bottom nav
    await expect(bottomNav).toHaveScreenshot('bottom-nav-mobile.png')
  })
})

test.describe('Visual Regression - Tablet (768x1024)', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
  })

  test('API Sources page', async ({ page }) => {
    await gotoWithMocks(page, '/swagger')
    await page.waitForSelector('.list-items')
    await expect(page).toHaveScreenshot('swagger-tablet.png', {
      fullPage: false,
      maxDiffPixelRatio: 0.02,
    })
  })
})

test.describe('Component Screenshots', () => {
  test('API Map with data - desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await gotoWithMocks(page, '/endpoints')
    
    // Wait for graph
    await page.waitForSelector('.vue-flow__nodes', { timeout: 10000 })
    await page.waitForTimeout(1500)
    
    // Screenshot of the map area only
    const mapContainer = page.locator('.maps-container')
    await expect(mapContainer).toHaveScreenshot('api-map-graph-desktop.png', {
      maxDiffPixelRatio: 0.03, // Graph layout may vary slightly
    })
  })

  test('Swagger list cards - mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await gotoWithMocks(page, '/swagger')
    
    // Wait for cards
    await page.waitForSelector('.list-card')
    
    // Screenshot first card
    const firstCard = page.locator('.list-card').first()
    await expect(firstCard).toHaveScreenshot('swagger-card-mobile.png')
  })
})
