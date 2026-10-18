// Product-list scales only: raw PRICE /100 => yuan; raw RATIO stays a fraction.
// No metric value is converted to a binary floating-point number.
export function shiftProductDecimal(
  value: string,
  places: -2 | 0 | 2,
): string | null {
  if (/^-0+(?:\.0+)?(?:e[+-]?\d+)?$/i.test(value)) value = value.slice(1)
  const match = /^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(value)
  if (!match) return null
  // Backend raw values use plain decimals. Scientific notation is needed only
  // for the existing finite Number-based input control's canonical strings.
  const exponent = Number(match[3] ?? 0)
  if (!Number.isInteger(exponent) || Math.abs(exponent) > 324) return null
  const digits = match[1]! + (match[2] ?? '')
  const point = match[1]!.length + exponent + places
  const shifted =
    point <= 0
      ? '0.' + '0'.repeat(-point) + digits
      : point >= digits.length
        ? digits + '0'.repeat(point - digits.length)
        : digits.slice(0, point) + '.' + digits.slice(point)
  const [whole, fraction = ''] = shifted.split('.')
  const integer = whole!.replace(/^0+(?=\d)/, '')
  const decimal = fraction.replace(/0+$/, '')
  return integer + (decimal ? '.' + decimal : '')
}

export function formatProductDecimal(
  value: string,
  unit: 'ratio' | 'yuan',
): string {
  const shifted = shiftProductDecimal(value, unit === 'ratio' ? 2 : 0)
  if (shifted === null) return '—'
  const [whole, fraction = ''] = shifted.split('.')
  // Positive values use decimal half-up at the final two-place presentation.
  // Full precision remains in value/rawValue and in SQL range comparisons.
  const hundredths = BigInt(whole! + fraction.padEnd(2, '0').slice(0, 2))
  const rounded = hundredths + ((fraction[2] ?? '0') >= '5' ? 1n : 0n)
  const integer = rounded / 100n
  const decimal = (rounded % 100n).toString().padStart(2, '0')
  return unit === 'ratio'
    ? integer.toString() + '.' + decimal + '%'
    : '¥' + integer.toLocaleString('zh-CN') + '.' + decimal
}
