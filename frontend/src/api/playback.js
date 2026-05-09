import { api } from './client.js'

export const playbackApi = {
  list:           ()              => api.get('/api/playback'),
  update:         (filePath, body) => api.patch(`/api/playback/${encodeURIComponent(filePath)}`, { body }),
  deleteOne:      (filePath)      => api.delete(`/api/playback/${encodeURIComponent(filePath)}`),
  clearAll:       ()              => api.delete('/api/playback'),
}
