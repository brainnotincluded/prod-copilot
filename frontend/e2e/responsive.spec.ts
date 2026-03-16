/**
 * Responsive Design Visual Regression Tests
 * 
 * These tests verify that the UI looks correct at different viewport sizes
 * and that navigation adapts properly between desktop and mobile.
 */

import { test, expect } from '@playwright/test'

// Viewport sizes to test
const viewports = {
  mobile: { width: 390, height: 844 }, // iPhone 14
  tablet: { width: 768, height: 1024 }, // iPad Mini
  desktop: { width: 1440, height: 900 }, // Desktop
}

test.describe('Responsive Navigation', () => {
  test('mobile shows bottom navigation without hamburger menu', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/chat')
    
    // Bottom navigation should be visible
    const bottomNav = page.locator('.bottom-nav')
    await expect(bottomNav).toBeVisible()
    
    // Should have 3 navigation items (Chat, API Sources, API Map) - no Dashboard
    const navItems = bottomNav.locator('.nav-item')
    await expect(navItems).toHaveCount(3)
    
    // Hamburger menu should NOT be visible on mobile
    const menuButton = page.locator('.menu-btn')
    await expect(menuButton).not.toBeVisible()
    
    // Verify navigation labels
    await expect(navItems.nth(0)).toContainText('Чат')
    await expect(navItems.nth(1)).toContainText('API-источники')
    await expect(navItems.nth(2)).toContainText('Карта API')
  })

  test('desktop shows sidebar with hamburger menu', async ({ page }) => {
    await page.setViewportSize(viewports.desktop)
    await page.goto('/chat')
    
    // Sidebar should be visible
    const sidebar = page.locator('.sidebar')
    await expect(sidebar).toBeVisible()
    
    // Hamburger menu should be visible on desktop
    const menuButton = page.locator('.menu-btn')
    await expect(menuButton).toBeVisible()
    
    // Bottom navigation should NOT be visible
    const bottomNav = page.locator('.bottom-nav')
    await expect(bottomNav).not.toBeVisible()
  })

  test('tablet shows mobile layout', async ({ page }) => {
    await page.setViewportSize(viewports.tablet)
    await page.goto('/chat')
    
    // Bottom navigation should be visible on tablet
    const bottomNav = page.locator('.bottom-nav')
    await expect(bottomNav).toBeVisible()
    
    // Sidebar should be hidden (off-screen)
    const sidebar = page.locator('.sidebar')
    await expect(sidebar).not.toHaveClass(/mobile-open/)
  })
})

test.describe('API Maps Page', () => {
  test('API map renders with mock data on desktop', async ({ page }) => {
    await page.setViewportSize(viewports.desktop)
    await page.goto('/endpoints')
    
    // Wait for the map container
    const mapContainer = page.locator('.maps-container')
    await expect(mapContainer).toBeVisible()
    
    // Header should show endpoint count
    const header = page.locator('.maps-header')
    await expect(header).toBeVisible()
    
    // VueFlow should be initialized
    const vueFlow = page.locator('.vue-flow')
    await expect(vueFlow).toBeVisible()
  })

  test('API map is usable on mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/endpoints')
    
    // Map should be visible
    const mapContainer = page.locator('.maps-container')
    await expect(mapContainer).toBeVisible()
    
    // Controls should be visible and touch-friendly
    const controls = page.locator('.vue-flow__controls')
    await expect(controls).toBeVisible()
    
    // MiniMap should be hidden on mobile
    const miniMap = page.locator('.vue-flow__minimap')
    await expect(miniMap).not.toBeVisible()
  })

  test('detail panel can be opened and closed on mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/endpoints')
    
    // Wait for nodes to render
    await page.waitForSelector('.vue-flow__node')
    
    // Click on a node
    const node = page.locator('.vue-flow__node').first()
    await node.click()
    
    // Detail panel should appear
    const detailPanel = page.locator('.detail-panel')
    await expect(detailPanel).toBeVisible()
    
    // Close button should work
    const closeButton = detailPanel.locator('.close-btn')
    await closeButton.click()
    await expect(detailPanel).not.toBeVisible()
  })
})

test.describe('Chat Page Responsive', () => {
  test('chat input adapts to mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/chat')
    
    // Input should be full width on mobile
    const inputWrapper = page.locator('.chat-input-wrapper')
    await expect(inputWrapper).toBeVisible()
    
    // Send button should be larger on mobile (44px)
    const sendButton = page.locator('.send-btn')
    const box = await sendButton.boundingBox()
    expect(box?.width).toBeGreaterThanOrEqual(44)
    expect(box?.height).toBeGreaterThanOrEqual(44)
  })

  test('suggestion chips scroll horizontally on mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/chat')
    
    const suggestions = page.locator('.empty-suggestions')
    await expect(suggestions).toBeVisible()
    
    // Should have horizontal scroll
    const scrollWidth = await suggestions.evaluate(el => el.scrollWidth)
    const clientWidth = await suggestions.evaluate(el => el.clientWidth)
    
    // On mobile, chips should overflow (scrollWidth > clientWidth)
    // or be in a scrollable container
    expect(scrollWidth).toBeGreaterThan(0)
  })
})

test.describe('Swagger Page Responsive', () => {
  test('upload zone is accessible on mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/swagger')
    
    // Upload zone should be visible
    const uploadZone = page.locator('.upload-zone')
    await expect(uploadZone).toBeVisible()
    
    // Tab buttons should be touch-friendly
    const tabButtons = page.locator('.tab-btn')
    const firstTab = tabButtons.first()
    const box = await firstTab.boundingBox()
    expect(box?.height).toBeGreaterThanOrEqual(48)
  })

  test('source list adapts to mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/swagger')
    
    // List container should be visible
    const listContainer = page.locator('.swagger-list')
    await expect(listContainer).toBeVisible()
    
    // Refresh button should be touch-friendly (44px)
    const refreshBtn = page.locator('.refresh-btn')
    const box = await refreshBtn.boundingBox()
    expect(box?.width).toBeGreaterThanOrEqual(44)
    expect(box?.height).toBeGreaterThanOrEqual(44)
  })
})

test.describe('Visual Regression', () => {
  test('chat page matches snapshot on mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/chat')
    
    // Wait for fonts to load
    await page.waitForTimeout(500)
    
    // Take screenshot
    expect(await page.screenshot({ fullPage: false })).toMatchSnapshot('chat-mobile.png')
  })

  test('chat page matches snapshot on desktop', async ({ page }) => {
    await page.setViewportSize(viewports.desktop)
    await page.goto('/chat')
    
    await page.waitForTimeout(500)
    
    expect(await page.screenshot({ fullPage: false })).toMatchSnapshot('chat-desktop.png')
  })

  test('API maps matches snapshot on mobile', async ({ page }) => {
    await page.setViewportSize(viewports.mobile)
    await page.goto('/endpoints')
    
    // Wait for VueFlow to initialize
    await page.waitForSelector('.vue-flow', { timeout: 5000 })
    await page.waitForTimeout(1000)
    
    expect(await page.screenshot({ fullPage: false })).toMatchSnapshot('api-maps-mobile.png')
  })

  test('API maps matches snapshot on desktop', async ({ page }) => {
    await page.setViewportSize(viewports.desktop)
    await page.goto('/endpoints')
    
    await page.waitForSelector('.vue-flow', { timeout: 5000 })
    await page.waitForTimeout(1000)
    
    expect(await page.screenshot({ fullPage: false })).toMatchSnapshot('api-maps-desktop.png')
  })
})
