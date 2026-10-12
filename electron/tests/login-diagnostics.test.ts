import assert from 'node:assert/strict'
import test from 'node:test'
import { EventEmitter } from 'node:events'
import { mkdtemp, readFile, readdir, rm, stat } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import type { WebContents } from 'electron'
import {
  LoginDiagnosticFile,
  rendererLoginDiagnostic,
  rendererLoginDiagnosticPrefix,
  safeLoginDiagnostic,
  installRendererLoginDiagnostics,
  createLoginDiagnosticRecorder,
  safeAccountProbes,
  loginNavigationClass,
  loginScriptErrorClass,
  type LoginDiagnostic,
} from '../services/login-diagnostics'

const correlationId = 'f6a068fd-2fce-4dca-8e01-dc26b15c4ea7'
const entry = {
  correlationId,
  source: 'renderer',
  phase: 'entry',
  event: 'start',
  bridgeAvailable: false,
  superAccount: true,
  teamSelected: false,
  platformSupported: true,
}
const message = rendererLoginDiagnosticPrefix + JSON.stringify(entry)

test('observation accepts only bounded known path/outcome metadata, never query, payload or a guessed CORS reason', () => {
  const probe = {
    probeIndex: 0,
    httpStatus: 200,
    elapsedMs: 14,
    requestFailed: false,
  }
  assert.deepEqual(safeAccountProbes([probe]), [probe])
  for (const invalid of [
    { ...probe, probeIndex: 9 },
    { ...probe, payload: 'private-fixture' },
    { ...probe, httpStatus: 0 },
    { ...probe, elapsedMs: -1 },
    { ...probe, requestFailed: 'private-fixture' },
  ])
    assert.deepEqual(safeAccountProbes([invalid]), [])
  assert.equal(
    loginNavigationClass(
      'https://compass.jinritemai.com/shop?token=private-fixture',
    ),
    'compass_shop',
  )
  assert.equal(
    loginNavigationClass('https://unknown.invalid/private-fixture'),
    'other_navigation',
  )
  assert.equal(loginScriptErrorClass('Failed to fetch'), 'JS_UNCLASSIFIED')
  assert.equal(
    loginScriptErrorClass(
      'Fetch has been blocked by CORS policy: private-fixture',
    ),
    'JS_CORS_POLICY',
  )
  const record = {
    ...entry,
    source: 'main',
    phase: 'account_probe',
    event: 'finish',
    pathClass: 'compass_shop_info_v2',
    httpStatus: 200,
    navigationSequence: 1,
    identityPresent: false,
    captureReady: false,
  }
  assert.ok(safeLoginDiagnostic(record))
  for (const invalid of [
    { ...record, pathClass: 'https://secret.invalid' },
    { ...record, identityPresent: 'private-fixture' },
    { ...record, navigationSequence: -1 },
    { ...record, scriptErrorCount: 21 },
    { ...record, body: 'private-fixture' },
  ])
    assert.equal(safeLoginDiagnostic(invalid), null)
  assert.equal(
    rendererLoginDiagnostic(
      rendererLoginDiagnosticPrefix + JSON.stringify(record),
      true,
      true,
    ),
    null,
  )
})

test('pre-IPC missing bridge/team entry survives strict production diagnostic reconstruction', () => {
  const record = rendererLoginDiagnostic(message, true, true)!
  assert.equal(record.bridgeAvailable, false)
  assert.equal(record.teamSelected, false)
  assert.equal(record.correlationId, correlationId)
  assert.equal(rendererLoginDiagnostic(message, false, true), null)
  assert.equal(rendererLoginDiagnostic(message, true, false), null)
  for (const extra of [
    { cookie: 'private-fixture' },
    { headers: {} },
    { url: 'private-fixture' },
    { payload: {} },
    { error: new Error('private-fixture') },
  ])
    assert.equal(
      rendererLoginDiagnostic(
        rendererLoginDiagnosticPrefix + JSON.stringify({ ...entry, ...extra }),
        true,
        true,
      ),
      null,
    )
  assert.equal(
    rendererLoginDiagnostic(message + ' '.repeat(2048), true, true),
    null,
  )
  assert.equal(
    rendererLoginDiagnostic(
      rendererLoginDiagnosticPrefix + '{invalid',
      true,
      true,
    ),
    null,
  )
  assert.equal(
    safeLoginDiagnostic({ ...entry, correlationId: 'private-fixture' }),
    null,
  )
  assert.equal(safeLoginDiagnostic({ ...entry, httpStatus: 900 }), null)
  assert.equal(
    safeLoginDiagnostic({ ...entry, teamSelected: 'private-fixture' }),
    null,
  )
  const safeError = safeLoginDiagnostic({
    ...entry,
    errorCode: 'private-fixture',
  })!
  assert.equal(safeError.errorCode, null)
})

test('installed main-frame listener ignores subframe, changed origin and forged Main phases without weakening security', () => {
  const mainFrame = { url: 'https://119.29.188.118/' }
  const contents = Object.assign(new EventEmitter(), {
    mainFrame,
    isDestroyed: () => false,
    getURL: () => mainFrame.url,
  })
  const records: LoginDiagnostic[] = []
  installRendererLoginDiagnostics(
    contents as unknown as WebContents,
    'https://119.29.188.118',
    (record) => records.push(record),
  )
  contents.emit('console-message', { message, frame: mainFrame })
  assert.equal(records.length, 1)
  contents.emit('console-message', { message, frame: { url: mainFrame.url } })
  mainFrame.url = 'https://untrusted.example/'
  contents.emit('console-message', { message, frame: mainFrame })
  mainFrame.url = 'https://119.29.188.118/'
  contents.emit('console-message', {
    message:
      rendererLoginDiagnosticPrefix +
      JSON.stringify({ ...entry, source: 'main', phase: 'session_metadata' }),
    frame: mainFrame,
  })
  contents.emit('console-message', {
    message: 'private unprefixed console fixture',
    frame: mainFrame,
  })
  assert.equal(records.length, 1)
})

test('packaged diagnostic recorder is enabled independently of DevTools and writes only rebuilt bounded records', async () => {
  const directory = await mkdtemp(
    path.join(os.tmpdir(), 'shop-login-diagnostics-'),
  )
  try {
    const sink = new LoginDiagnosticFile(directory, 1024)
    let devCalls = 0
    const record = createLoginDiagnosticRecorder(sink, true, () => {
      devCalls++
    })
    record({
      ...entry,
      payload: 'private-fixture',
    } as unknown as LoginDiagnostic)
    await sink.flush()
    assert.equal(
      await stat(sink.filePath)
        .then(() => true)
        .catch(() => false),
      false,
    )
    for (let index = 0; index < 12; index++) record(entry as LoginDiagnostic)
    await sink.flush()
    const files = await readdir(path.join(directory, 'diagnostics'))
    assert.deepEqual(files.sort(), ['shop-login.jsonl', 'shop-login.jsonl.1'])
    assert.equal(devCalls, 0)
    for (const file of files) {
      const filePath = path.join(directory, 'diagnostics', file)
      assert.ok((await stat(filePath)).size <= 1024)
      const content = await readFile(filePath, 'utf8')
      assert.ok(!content.includes('private-fixture'))
      for (const line of content.trim().split('\n')) {
        const raw = JSON.parse(line)
        assert.equal(safeLoginDiagnostic(raw, true)?.timestamp, raw.timestamp)
        assert.equal(raw.correlationId, correlationId)
      }
    }
  } finally {
    assert.ok(
      path
        .resolve(directory)
        .startsWith(
          path.join(path.resolve(os.tmpdir()), 'shop-login-diagnostics-'),
        ),
    )
    await rm(directory, { recursive: true, force: true })
  }
})
