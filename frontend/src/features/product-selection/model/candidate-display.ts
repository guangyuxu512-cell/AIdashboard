import dayjs from 'dayjs'

// List and detail use the same nullable value formatting; zero is not missing.
export const formatCandidateDate = (value: string | null) =>
  value === null ? '—' : dayjs(value).format('YYYY-MM-DD')
export const formatReviewRate = (value: number | null) =>
  value === null ? '—' : `${(value * 100).toFixed(2)}%`
