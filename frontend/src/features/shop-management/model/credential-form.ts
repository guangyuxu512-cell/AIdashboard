import { z } from 'zod'

import type { VerificationChannel } from '@/entities/credential'

export interface CredentialFormValue {
  loginIdentifier: string
  password: string
  preferredVerificationChannel: VerificationChannel
}

export type CredentialFormErrors = Partial<
  Record<keyof CredentialFormValue, string>
>

export const EMPTY_CREDENTIAL_FORM: CredentialFormValue = {
  loginIdentifier: '',
  password: '',
  preferredVerificationChannel: 'manual',
}

export const VERIFICATION_CHANNEL_OPTIONS = [
  { label: '人工', value: 'manual' },
  { label: '邮箱', value: 'email' },
  { label: '短信硬件', value: 'sms_hardware' },
]

export function createCredentialFormSchema(configured: boolean) {
  return z.object({
    loginIdentifier: z
      .string()
      .trim()
      .max(320, '登录账号最多 320 个字符')
      .refine((value) => configured || value.length > 0, '请输入登录账号'),
    password: z
      .string()
      .max(1000, '登录密码最多 1000 个字符')
      .refine((value) => configured || value.length > 0, '请输入登录密码'),
    preferredVerificationChannel: z.enum([
      'manual',
      'email',
      'sms_hardware',
    ]),
  })
}
