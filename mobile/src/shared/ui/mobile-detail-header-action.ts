import {
  inject,
  provide,
  shallowRef,
  type InjectionKey,
  type ShallowRef,
} from 'vue'

import type { MobileIconName } from '@/shared/icons'

export interface MobileDetailHeaderAction {
  label: string
  icon: MobileIconName
  run: () => void
}

export interface MobileDetailHeaderActionController {
  action: ShallowRef<MobileDetailHeaderAction | null>
  setAction: (action: MobileDetailHeaderAction | null) => void
}

const mobileDetailHeaderActionKey: InjectionKey<MobileDetailHeaderActionController> =
  Symbol('mobile-detail-header-action')

export function provideMobileDetailHeaderAction(): MobileDetailHeaderActionController {
  const action = shallowRef<MobileDetailHeaderAction | null>(null)
  const controller: MobileDetailHeaderActionController = {
    action,
    setAction(nextAction) {
      action.value = nextAction
    },
  }
  provide(mobileDetailHeaderActionKey, controller)
  return controller
}

export function useMobileDetailHeaderAction(): MobileDetailHeaderActionController | null {
  return inject(mobileDetailHeaderActionKey, null)
}
