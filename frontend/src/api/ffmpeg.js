import { api, createWs } from './client.js'

export const ffmpegApi = {
  status:     ()       => api.get('/api/ffmpeg/status'),
  install:    ()       => api.post('/api/ffmpeg/install'),
  installWs:  (taskId) => createWs(`/api/ffmpeg/install/ws/${taskId}`),
}
