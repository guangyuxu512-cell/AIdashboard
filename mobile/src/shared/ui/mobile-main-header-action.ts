import {
  inject,
  provide,
  shallowRef,
  type InjectionKey,
  type ShallowRef,
} from 'vue'

export interface MobileMainHeaderAction {
  label: string
  run: () => void
}

export interface MobileMainHeaderActionController {
  action: ShallowRef<MobileMainHeaderAction | null>
  setAction: (action: MobileMainHeaderAction | null) => void
}

const mobileMainHeaderActionKey: InjectionKey<MobileMainHeaderActionController> =
  Symbol('mobile-main-header-action')

export function provideMobileMainHeaderAction(): MobileMainHeaderActionController {
  const action = shallowRef<MobileMainHeaderAction | null>(null)
  const controller: MobileMainHeaderActionController = {
    action,
    setAction(nextAction) {
      action.value = nextAction
    },
  }
  provide(mobileMainHeaderActionKey, controller)
  return controller
}

export function useMobileMainHeaderAction(): MobileMainHeaderActionController | null {
  return inject(mobileMainHeaderActionKey, null)
}
