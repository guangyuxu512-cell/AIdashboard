export type FieldWidth = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'full'

export type OverlaySize = 'sm' | 'md' | 'lg'

export type AppOptionValue = string | number

export interface AppOption {
  label: string
  value: AppOptionValue
  disabled?: boolean
}
