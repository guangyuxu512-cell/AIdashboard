import type { GlobalThemeOverrides } from 'naive-ui'

function readCssToken(name: string): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  if (!value) {
    throw new Error(`Missing required design token: ${name}`)
  }
  return value
}

export function createNaiveThemeOverrides(): GlobalThemeOverrides {
  const color = (name: string) => readCssToken(`--color-${name}`)

  return {
    common: {
      fontFamily: 'var(--font-family-base)',
      fontSize: 'var(--font-size-body)',
      primaryColor: color('primary'),
      primaryColorHover: color('primary-hover'),
      primaryColorPressed: color('primary-pressed'),
      infoColor: color('info'),
      successColor: color('success'),
      warningColor: color('warning'),
      errorColor: color('error'),
      borderRadius: 'var(--radius-control)',
      borderColor: color('border-default'),
      textColorBase: color('text-primary'),
      textColor1: color('text-primary'),
      textColor2: color('text-secondary'),
      textColor3: color('text-muted'),
    },
    Button: {
      heightSmall: 'var(--control-height-compact)',
      heightMedium: 'var(--control-height-default)',
      heightLarge: 'var(--control-height-large)',
      borderRadiusSmall: 'var(--radius-control)',
      borderRadiusMedium: 'var(--radius-control)',
      borderRadiusLarge: 'var(--radius-control)',
      fontSizeMedium: 'var(--font-size-body)',
    },
    Input: {
      heightSmall: 'var(--control-height-compact)',
      heightMedium: 'var(--control-height-default)',
      heightLarge: 'var(--control-height-large)',
      borderRadius: 'var(--radius-control)',
      fontSizeMedium: 'var(--font-size-body)',
    },
    DataTable: {
      borderColor: color('border-default'),
      borderRadius: 'var(--radius-card)',
      thColor: color('bg-subtle'),
    thTextColor: color('text-secondary'),
    thFontWeight: 'var(--font-weight-semibold)',
    thPaddingMedium: 'var(--space-2) var(--space-3)',
    tdTextColor: color('text-primary'),
    tdPaddingMedium: 'var(--space-3)',
    },
    Pagination: {
      itemSizeMedium: 'var(--control-height-compact)',
      itemBorderRadius: 'var(--radius-control)',
    },
    Drawer: {
      borderRadius: 'var(--radius-dialog)',
      color: color('bg-card'),
      boxShadow: 'var(--shadow-overlay)',
      bodyPadding: 'var(--space-6)',
      headerPadding: 'var(--space-5) var(--space-6)',
      footerPadding: 'var(--space-4) var(--space-6)',
    },
    Modal: {
      color: color('bg-card'),
      boxShadow: 'var(--shadow-overlay)',
    },
    Tabs: {
      tabFontSizeMedium: 'var(--font-size-body)',
      tabGapMediumLine: 'var(--space-6)',
      tabFontWeightActive: 'var(--font-weight-semibold)',
    },
  }
}
