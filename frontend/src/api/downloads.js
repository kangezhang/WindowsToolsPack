import { api, createWs } from './client.js'

export const downloadsApi = {
  fetchInfo:      (url)    => api.post('/api/downloads/fetch-info', { body: { url } }),
  fetchInfoWs:    (taskId) => createWs(`/api/downloads/fetch-info/ws/${taskId}`),

  createTask:     (payload) => api.post('/api/downloads/tasks', { body: payload }),
  taskWs:         (taskId)  => createWs(`/api/downloads/tasks/ws/${taskId}`),

  listTasks:      ()        => api.get('/api/downloads/tasks'),
  cancelTask:     (taskId)  => api.post(`/api/downloads/tasks/${taskId}/cancel`),
  clearFinished:  ()        => api.delete('/api/downloads/tasks/finished'),

  getSettings:    ()        => api.get('/api/downloads/settings'),
  updateSettings: (payload) => api.put('/api/downloads/settings', { body: payload }),
}
