import { createOperatingDashboardFixture } from '../__fixtures__/operating-dashboard.fixture'

import { buildOperatingDashboardRead } from './dashboard'
import type {
  OperatingDashboardMockSource,
  OperatingDashboardRefreshResult,
} from './types'

const REFRESH_FAILURE_SHOP_ID = 'dashboard-shop-005'

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

/**
 * A development-only interaction source. It does not emulate a Backend route,
 * platform request, signer call, or durable collection record.
 */
export function createOperatingDashboardMockSource(
  now = new Date(),
): OperatingDashboardMockSource {
  const records = createOperatingDashboardFixture(now)
  const failedAttempts = new Set<string>()

  return {
    async read(filters) {
      await delay(120)
      return buildOperatingDashboardRead(records, filters, now)
    },
    async refresh(filters): Promise<OperatingDashboardRefreshResult> {
      await delay(320)
      const read = buildOperatingDashboardRead(records, filters, now)
      const rows = read.tableRows
      const failedRows = rows.filter(
        (row) =>
          row.shopId === REFRESH_FAILURE_SHOP_ID &&
          !failedAttempts.has(row.shopId),
      )
      failedRows.forEach((row) => failedAttempts.add(row.shopId))

      if (rows.length === 0) {
        return {
          status: 'failed',
          attemptedShopCount: 0,
          refreshedShopCount: 0,
          failedShopNames: [],
        }
      }
      if (failedRows.length === rows.length) {
        return {
          status: 'failed',
          attemptedShopCount: rows.length,
          refreshedShopCount: 0,
          failedShopNames: failedRows.map((row) => row.shopName),
        }
      }
      if (failedRows.length > 0) {
        return {
          status: 'partial_failure',
          attemptedShopCount: rows.length,
          refreshedShopCount: rows.length - failedRows.length,
          failedShopNames: failedRows.map((row) => row.shopName),
        }
      }
      return {
        status: 'completed',
        attemptedShopCount: rows.length,
        refreshedShopCount: rows.length,
        failedShopNames: [],
      }
    },
  }
}
