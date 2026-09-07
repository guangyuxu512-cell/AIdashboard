import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isManagementLoginCompleteInput,
  isManagementLoginOpenInput,
} from '../types'
import { shouldPreserveCapturedLogin } from '../services/management-login-lifecycle'
import {
  parseManagementLoginProfile,
  resolveManagementLoginPartition,
} from '../services/management-login-profile'
import { PddPlatformAuthAdapter } from '../services/pdd-platform-auth-adapter'
import type { Cookie, Session } from 'electron'

const attemptId = '00000000-0000-4000-8000-000000000001'

test('management login IPC only accepts registered platform and typed attempt', () => {
  const teamId = '00000000-0000-4000-8000-000000000004'
  assert.equal(
    isManagementLoginOpenInput({ platform: 'douyin', teamId }),
    true,
  )
  assert.equal(
    isManagementLoginOpenInput({ platform: 'douyin', teamId, attemptId }),
    true,
  )
  assert.equal(
    isManagementLoginOpenInput({
      platform: 'douyin',
      teamId,
      recovery: {
        shopId: '00000000-0000-4000-8000-000000000002',
        leaseId: '00000000-0000-4000-8000-000000000003',
        expectedVersion: 3,
      },
    }),
    true,
  )
  assert.equal(isManagementLoginOpenInput({ platform: 'pdd', teamId }), true)
  assert.equal(
    isManagementLoginOpenInput({
      platform: 'douyin',
      teamId,
      attemptId: '../profile',
    }),
    false,
  )
  assert.equal(isManagementLoginOpenInput({ platform: 'douyin' }), false)
})

test('management login recovery reuses only a valid local profile mapping', () => {
  const mapping = parseManagementLoginProfile(
    {
      platform: 'douyin',
      partition: `persist:management-login-${attemptId}`,
      updatedAt: '2026-08-21T12:00:00Z',
    },
    'douyin',
  )
  assert.deepEqual(resolveManagementLoginPartition(attemptId, mapping), {
    partition: `persist:management-login-${attemptId}`,
    profileReused: true,
  })
  assert.deepEqual(resolveManagementLoginPartition(attemptId, null), {
    partition: `persist:management-login-${attemptId}`,
    profileReused: false,
  })
  assert.equal(
    parseManagementLoginProfile(
      {
        platform: 'douyin',
        partition: 'persist:../../unsafe',
        updatedAt: '2026-08-21T12:00:00Z',
      },
      'douyin',
    ),
    null,
  )
})

test('management login completion rejects untyped or arbitrary execution input', () => {
  assert.equal(
    isManagementLoginCompleteInput({
      attemptId,
      loginIdentifier: 'account@example.com',
      secret: 'password',
      preferredVerificationChannel: 'manual',
    }),
    true,
  )
  assert.equal(
    isManagementLoginCompleteInput({
      attemptId,
      loginIdentifier: 'account@example.com',
      secret: 'password',
      preferredVerificationChannel: 'manual',
      script: 'require("child_process").exec("whoami")',
    }),
    false,
  )
  assert.equal(
    isManagementLoginCompleteInput({
      attemptId,
      loginIdentifier: '',
      secret: 'password',
      preferredVerificationChannel: 'manual',
    }),
    false,
  )
})

test('management login only preserves capture for Main initiated auto close', () => {
  assert.equal(
    shouldPreserveCapturedLogin({
      status: 'identified',
      systemCloseRequested: true,
      sessionCaptured: true,
    }),
    true,
  )
  assert.equal(
    shouldPreserveCapturedLogin({
      status: 'identified',
      systemCloseRequested: false,
      sessionCaptured: true,
    }),
    false,
  )
  assert.equal(
    shouldPreserveCapturedLogin({
      status: 'waiting',
      systemCloseRequested: true,
      sessionCaptured: false,
    }),
    false,
  )
})

test('PDD waits for the authenticated session cookies applicable to identity', async () => {
  const adapter = new PddPlatformAuthAdapter()
  let queriedUrl = ''
  const loginSession = {
    cookies: {
      get: async ({ url }: { url: string }) => {
        queriedUrl = url
        return [
          cookie('api_uid'),
          cookie('_nano_fp'),
          cookie('webp'),
        ]
      },
    },
  } as unknown as Session

  const beforeAuthentication = await adapter.detectLoginStatus(loginSession, 1)

  assert.equal(beforeAuthentication.readyForCapture, false)
  assert.equal(
    queriedUrl,
    'https://mms.pinduoduo.com/earth/api/merchant/queryMerchantInfoByMallId',
  )

  loginSession.cookies.get = async () => [
    cookie('api_uid'),
    cookie('_nano_fp'),
    cookie('webp'),
    cookie('JSESSIONID'),
    cookie('PASS_ID'),
  ]

  const afterAuthentication = await adapter.detectLoginStatus(loginSession, 1)

  assert.equal(afterAuthentication.readyForCapture, true)
})

function cookie(name: string): Cookie {
  return {
    name,
    value: 'test',
    domain: 'mms.pinduoduo.com',
    path: '/',
    secure: true,
    httpOnly: true,
    sameSite: 'lax',
  } as Cookie
}
