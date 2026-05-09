import { api, createWs } from './client.js'

export const diskApi = {
  startScan: (path) => api.post('/api/disk/scan', { body: { path } }),
  openWs:    (taskId) => createWs(`/api/disk/ws/${taskId}`),
}
