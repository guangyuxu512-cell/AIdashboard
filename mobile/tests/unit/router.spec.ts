import { describe, expect, it, vi } from 'vitest'
import type { NavigationGuard, Router } from 'vue-router'

import { installRouteAccessGuards } from '@/app/router/access'
import { createMobileRouter } from '@/app/router'
import { createMobileRoutes, MOBILE_ROUTE_NAMES } from '@/app/router/routes'

describe('mobile router', () => {
  it('declares explicit access metadata for every route', () => {
    const routes = createMobileRoutes({ includeFoundation: true })

    for (const route of routes) {
      expect(route.meta).toEqual(
        expect.objectContaining({
          title: expect.any(String),
          requiresAuth: expect.any(Boolean),
          permission: null,
        }),
      )
    }
  })

  it('keeps the foundation route out of a production runtime by default', () => {
    const productionRoutes = createMobileRoutes({
      runtimeIsDevelopment: false,
    })

    expect(
      productionRoutes.some(
        (route) => route.name === MOBILE_ROUTE_NAMES.foundation,
      ),
    ).toBe(false)
    expect(productionRoutes.map((route) => route.path)).toEqual([
      '/',
      '/tasks',
      '/tasks/:taskId',
    ])
  })

  it('registers task list and detail with the frozen public route metadata', () => {
    const routes = createMobileRoutes({ runtimeIsDevelopment: false })

    for (const routeName of [
      MOBILE_ROUTE_NAMES.tasks,
      MOBILE_ROUTE_NAMES.taskDetail,
    ]) {
      const route = routes.find((candidate) => candidate.name === routeName)
      expect(route?.meta).toEqual(
        expect.objectContaining({
          requiresAuth: false,
          permission: null,
        }),
      )
    }
  })

  it('registers the foundation route only when explicitly enabled', () => {
    const developmentRoutes = createMobileRoutes({ includeFoundation: true })

    expect(
      developmentRoutes.find(
        (route) => route.name === MOBILE_ROUTE_NAMES.foundation,
      )?.path,
    ).toBe('/__foundation')
  })

  it('uses hash history', () => {
    const router = createMobileRouter({ includeFoundation: false })

    expect(router.options.history.createHref('/')).toContain('#/')
  })

  it('installs named Auth and Permission guards in a fixed order', () => {
    const removeAuthGuard = vi.fn()
    const removePermissionGuard = vi.fn()
    const beforeEach = vi
      .fn()
      .mockReturnValueOnce(removeAuthGuard)
      .mockReturnValueOnce(removePermissionGuard)
    const router = { beforeEach } as unknown as Router
    const authGuard = vi.fn(() => true) as NavigationGuard
    const permissionGuard = vi.fn(() => true) as NavigationGuard

    const remove = installRouteAccessGuards(router, {
      authGuard,
      permissionGuard,
    })

    expect(beforeEach.mock.calls).toEqual([[authGuard], [permissionGuard]])

    remove()
    expect(removePermissionGuard).toHaveBeenCalledOnce()
    expect(removeAuthGuard).toHaveBeenCalledOnce()
  })

  it('does not install fake access guards when none are supplied', () => {
    const beforeEach = vi.fn()
    const router = { beforeEach } as unknown as Router

    installRouteAccessGuards(router, {})

    expect(beforeEach).not.toHaveBeenCalled()
  })
})
