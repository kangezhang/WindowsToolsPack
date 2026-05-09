import { api, createWs } from './client.js'

function getBase() {
  if (typeof window !== 'undefined' && window.__TOOLPACK_API_BASE__) {
    return window.__TOOLPACK_API_BASE__
  }
  return ''
}

export const galleryApi = {
  startScan:  (path, recursive = true) =>
    api.post('/api/gallery/scan', { params: { path, recursive } }),
  scanWs:     (taskId) => createWs(`/api/gallery/scan/ws/${taskId}`),

  thumbnailUrl: (path, size = 200) => {
    const base = getBase()
    const token = typeof window !== 'undefined' ? (window.__TOOLPACK_TOKEN__ || '') : ''
    const qs = new URLSearchParams({ path, size })
    if (token) qs.set('token', token)
    return `${base}/api/gallery/thumbnail?${qs}`
  },

  openFile: (path) => api.post('/api/gallery/open', { params: { path } }),
}
