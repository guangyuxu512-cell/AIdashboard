export function isAiAssetsVisualMockEnabled(
  isDevelopment: boolean,
  queryValue: unknown,
): boolean {
  return isDevelopment && queryValue === '1'
}
