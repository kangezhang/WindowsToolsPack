import { api } from './client.js'

export const contextMenuApi = {
  list:    ()               => api.get('/api/context-menu'),
  enable:  (registryPaths) => api.post('/api/context-menu/enable',  { body: { registry_paths: registryPaths } }),
  disable: (registryPaths) => api.post('/api/context-menu/disable', { body: { registry_paths: registryPaths } }),
  remove:  (registryPaths) => api.delete('/api/context-menu',       { body: { registry_paths: registryPaths } }),
}
