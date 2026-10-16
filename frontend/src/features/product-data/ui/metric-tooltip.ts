// Reuse the existing Tooltip contentStyle API and semantic width/safe-gap tokens.
export const PRODUCT_METRIC_TOOLTIP_STYLE = {
  maxWidth:
    'min(var(--field-width-xl), calc(100vw - 2 * var(--overlay-viewport-safe-gap)))',
  whiteSpace: 'normal',
  overflowWrap: 'anywhere',
} as const
