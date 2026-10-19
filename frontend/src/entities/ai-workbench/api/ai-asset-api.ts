import {
  getAssetContentUrl,
  getAssetThumbnailUrl,
  uploadAssetFile,
} from '@/entities/asset/api/asset-api'
import { httpClient } from '@/shared/api'

const basePath = '/api/v1/ai-workbench/assets'

export const getAiAssetContentUrl = (id: string): string =>
  getAssetContentUrl(id, basePath)
export const getAiAssetThumbnailUrl = (id: string): string =>
  getAssetThumbnailUrl(id, basePath)

export const aiAssetApi = {
  upload: (file: File) => uploadAssetFile(file, basePath),
  cleanup: async (id: string): Promise<void> => {
    await httpClient.delete(`${basePath}/${encodeURIComponent(id)}`)
  },
}
