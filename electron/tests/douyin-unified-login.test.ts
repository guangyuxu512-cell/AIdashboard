import assert from 'node:assert/strict'
import test from 'node:test'
import type { BrowserWindow, Session } from 'electron'
import { DouyinUnifiedLogin } from '../services/douyin-unified-login'
import type { PlatformAuthAdapter } from '../services/platform-auth-adapter'

test('two shop windows keep their own session and never exchange identities', async () => {
  const sessions = [{ name: 'shop-a' }, { name: 'shop-b' }] as unknown as Session[]
  const visits: string[][] = [[], []]
  const windows = sessions.map((session, index) => {
    let url = 'https://compass.jinritemai.com/shop'
    return {
      webContents: { id: index + 1, session, getURL: () => url, isLoadingMainFrame: () => false },
      loadURL: async (next: string) => { visits[index]!.push(next); url = next },
    } as unknown as BrowserWindow
  })
  const adapter: PlatformAuthAdapter = {
    platformCode: 'douyin',
    loginUrl: 'https://compass.jinritemai.com/shop',
    loginWindowTitle: 'fixture',
    async detectLoginStatus(session) {
      const id = session === sessions[0] ? 'shop-a' : 'shop-b'
      return { readyForCapture: true, identity: { platform: 'douyin', platformShopId: id, shopDisplayName: id }, message: '' }
    },
    async merchantCookieFingerprint(session) { return session === sessions[0] ? 'fp-a' : 'fp-b' },
    async detectMerchantIdentity(id) { return { status: 'confirmed', platformShopId: id === 1 ? 'shop-a' : 'shop-b' } },
    async captureSession() { throw new Error('capture belongs to service') },
  }
  const flows = windows.map((window) => new DouyinUnifiedLogin(window, adapter, () => true, () => 0, () => true, () => {}))
  for (const flow of flows) assert.equal((await flow.advance()).readyForCapture, false)
  assert.equal((await flows[0]!.advance()).identity?.platformShopId, 'shop-a')
  assert.equal((await flows[1]!.advance()).identity?.platformShopId, 'shop-b')
  for (const visit of visits) assert.deepEqual(visit, [
    'https://fxg.jinritemai.com/ffa/g/create',
  ])
})
