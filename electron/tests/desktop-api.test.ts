import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isManagementLoginCompleteInput,
  isManagementLoginOpenInput,
} from '../types'

const attemptId = '00000000-0000-4000-8000-000000000001'

test('management login IPC only accepts registered platform and typed attempt', () => {
  assert.equal(isManagementLoginOpenInput({ platform: 'douyin' }), true)
  assert.equal(
    isManagementLoginOpenInput({ platform: 'douyin', attemptId }),
    true,
  )
  assert.equal(isManagementLoginOpenInput({ platform: 'pdd' }), false)
  assert.equal(
    isManagementLoginOpenInput({ platform: 'douyin', attemptId: '../profile' }),
    false,
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
