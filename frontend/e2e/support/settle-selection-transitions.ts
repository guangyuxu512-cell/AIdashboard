import { expect, type Page } from '@playwright/test'

// Wait for the existing transition before capturing rendered pixels.
export async function settleSelectionTransitions(page: Page) {
  await expect
    .poll(() =>
      page
        .locator('body')
        .evaluate(
          (element) =>
            element
              .getAnimations({ subtree: true })
              .filter(
                (animation) =>
                  animation.playState === 'running' &&
                  animation.effect?.getTiming().iterations !== Infinity,
              ).length,
        ),
    )
    .toBe(0)
}
