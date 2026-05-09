import { api } from './client.js'

export const systemApi = {
  getInfo:           ()  => api.get('/api/system/info'),
  enableAutostart:   ()  => api.post('/api/system/autostart/enable'),
  disableAutostart:  ()  => api.post('/api/system/autostart/disable'),
  elevate:           ()  => api.post('/api/system/elevate'),
}
