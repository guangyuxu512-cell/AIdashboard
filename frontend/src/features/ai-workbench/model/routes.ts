export const AI_WORKBENCH_ROUTES = {
  generate: {
    name: 'ai-workbench-generate',
    path: '/ai-workbench/generate',
    label: 'AI生图',
  },
  assets: {
    name: 'ai-workbench-assets',
    path: '/ai-workbench/assets',
    label: '素材库',
  },
  templates: {
    name: 'ai-workbench-templates',
    path: '/ai-workbench/templates',
    label: '模板库',
  },
  records: {
    name: 'ai-workbench-records',
    path: '/ai-workbench/records',
    label: '生成记录',
  },
} as const

export const AI_WORKBENCH_NAVIGATION = [
  AI_WORKBENCH_ROUTES.generate,
  AI_WORKBENCH_ROUTES.assets,
  AI_WORKBENCH_ROUTES.templates,
  AI_WORKBENCH_ROUTES.records,
] as const
