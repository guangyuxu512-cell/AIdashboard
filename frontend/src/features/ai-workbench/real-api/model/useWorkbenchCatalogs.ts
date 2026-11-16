import { useQuery } from '@tanstack/vue-query'

import {
  aiWorkbenchApi,
  aiWorkbenchQueryKeys,
  useWorkbenchModelsQuery,
} from '@/entities/ai-workbench'

import {
  mapGenerationProduct,
  mapGenerationTemplateGroup,
  mapWorkbenchModel,
} from './mappers'

export function useGenerationCatalogs() {
  const modelsQuery = useWorkbenchModelsQuery()
  const templatesQuery = useQuery({
    queryKey: [...aiWorkbenchQueryKeys.templates, 'generation-catalog'],
    queryFn: async () => {
      const groups = await aiWorkbenchApi.listAllTemplateGroups({
        enabled: true,
      })
      return Promise.all(
        groups.map((group) =>
          aiWorkbenchApi.getTemplateGroup(group.template_group_id),
        ),
      )
    },
    select: (groups) => groups.map(mapGenerationTemplateGroup),
  })
  const productsQuery = useQuery({
    queryKey: [...aiWorkbenchQueryKeys.materials, 'generation-catalog'],
    queryFn: async () => {
      const groups = await aiWorkbenchApi.listAllProductMaterialGroups({
        enabled: true,
      })
      return Promise.all(
        groups.map((group) =>
          aiWorkbenchApi.getProductMaterialGroup(group.material_group_id),
        ),
      )
    },
    select: (groups) => groups.map(mapGenerationProduct),
  })

  return {
    modelsQuery,
    templatesQuery,
    productsQuery,
    models: () => (modelsQuery.data.value ?? []).map(mapWorkbenchModel),
    templates: () => templatesQuery.data.value ?? [],
    products: () => productsQuery.data.value ?? [],
  }
}
