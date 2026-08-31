export function isAiTemplatesVisualMockEnabled(
  isDevelopment: boolean,
  queryValue: unknown,
): boolean {
  return isDevelopment && queryValue === '1'
}
