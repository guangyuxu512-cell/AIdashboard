export interface HumanRequestContext {
  getActiveTeamId?: () => string | null
  onSessionInvalid?: () => Promise<void> | void
}

let humanRequestContext: HumanRequestContext = {}

export function configureHumanRequestContext(
  context: HumanRequestContext,
): void {
  humanRequestContext = context
}

export function getHumanRequestContext(): Readonly<HumanRequestContext> {
  return humanRequestContext
}
