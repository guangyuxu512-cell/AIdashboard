import { afterEach, describe, expect, it } from 'vitest'

import {
  queryClient,
  resetQueriesForActorContextChange,
} from './query-client'

describe('query client actor context reset', () => {
  afterEach(() => queryClient.clear())

  it('removes cached data from the previous active team', async () => {
    queryClient.setQueryData(['assets', 'list'], { items: ['team-a'] })

    await resetQueriesForActorContextChange()

    expect(queryClient.getQueryData(['assets', 'list'])).toBeUndefined()
  })
})
