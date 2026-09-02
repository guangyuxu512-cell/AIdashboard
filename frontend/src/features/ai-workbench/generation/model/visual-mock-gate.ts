export function isAiGenerationVisualMockEnabled(
  isDevelopment: boolean,
  queryValue: unknown,
): boolean {
  return isDevelopment && queryValue === '1'
}
