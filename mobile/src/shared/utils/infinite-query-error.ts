export type InfiniteQueryErrorKind =
  'none' | 'initial' | 'background' | 'next-page'

export function classifyInfiniteQueryError(options: {
  hasSuccessfulData: boolean
  isError: boolean
  isFetchNextPageError: boolean
}): InfiniteQueryErrorKind {
  if (!options.isError) return 'none'
  if (!options.hasSuccessfulData) return 'initial'
  return options.isFetchNextPageError ? 'next-page' : 'background'
}
