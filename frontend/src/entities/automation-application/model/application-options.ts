import type { SelectOption } from 'naive-ui'

import type { YingdaoApplicationOptionDto } from '../api/contracts'

export function buildYingdaoApplicationSelectOptions(
  applications: YingdaoApplicationOptionDto[],
): SelectOption[] {
  const nameCounts = new Map<string, number>()
  for (const application of applications) {
    nameCounts.set(
      application.app_name,
      (nameCounts.get(application.app_name) ?? 0) + 1,
    )
  }
  return applications.map((application) => ({
    label:
      (nameCounts.get(application.app_name) ?? 0) > 1
        ? `${application.app_name} · ${application.app_id}`
        : application.app_name,
    value: application.app_id,
  }))
}
