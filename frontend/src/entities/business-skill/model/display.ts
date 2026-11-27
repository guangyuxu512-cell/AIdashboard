const skillNames: Record<string, { label: string; oldNames?: string[] }> = {
  'douyin.merchant_products': { label: '抖店商品管理' },
  'douyin.compass_selection': { label: '罗盘选品' },
  'douyin.category_schema': { label: '商品类目与预检' },
  'system.rpa_inventory_diagnostic': { label: 'RPA 店铺连接诊断' },
  'system.echo': { label: '消息回显（测试）', oldNames: ['Echo'] },
  'system.sleep': { label: '等待（测试）', oldNames: ['Sleep'] },
}

/** Keep server-provided names and IDs stable while naming legacy skill IDs. */
export function formatSkillName(skillId: string, displayName?: string | null): string {
  const name = displayName?.trim() ?? ''
  const known = Object.hasOwn(skillNames, skillId) ? skillNames[skillId] : undefined
  if (known && (!name || name === skillId || known.oldNames?.includes(name))) return known.label
  return name || skillId
}
