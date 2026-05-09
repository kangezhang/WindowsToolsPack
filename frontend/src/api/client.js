/**
 * 统一 API 客户端
 * - 自动注入 X-Local-Token header
 * - 基础路径通过 window.__TOOLPACK_API_BASE__ 注入（Electron 环境）
 *   或 Vite proxy（开发环境）
 */

function getBase() {
  if (typeof window !== 'undefined' && window.__TOOLPACK_API_BASE__) {
    return window.__TOOLPACK_API_BASE__
  }
  return ''  // dev: 通过 Vite proxy 转发
}

function getToken() {
  if (typeof window !== 'undefined' && window.__TOOLPACK_TOKEN__) {
    return window.__TOOLPACK_TOKEN__
  }
  return ''
}

async function request(method, path, { body, params, skipAuth = false } = {}) {
  const base = getBase()
  let url = base + path

  if (params) {
    const qs = new URLSearchParams(params).toString()
    if (qs) url += '?' + qs
  }

  const headers = { 'Content-Type': 'application/json' }
  if (!skipAuth) {
    const token = getToken()
    if (token) headers['X-Local-Token'] = token
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      msg = data.detail || data.error || msg
    } catch {}
    const err = new Error(msg)
    err.status = res.status
    throw err
  }

  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    return res.json()
  }
  return res
}

export const api = {
  get:    (path, opts) => request('GET',    path, opts),
  post:   (path, opts) => request('POST',   path, { body: opts?.body, params: opts?.params, skipAuth: opts?.skipAuth }),
  put:    (path, opts) => request('PUT',    path, { body: opts?.body, params: opts?.params }),
  patch:  (path, opts) => request('PATCH',  path, { body: opts?.body, params: opts?.params }),
  delete: (path, opts) => request('DELETE', path, { body: opts?.body, params: opts?.params }),
}

/**
 * 创建 WebSocket 连接
 * @param {string} path  e.g. "/api/disk/ws/xxx"
 * @returns {WebSocket}
 */
export function createWs(path) {
  const base = getBase()
  // 将 http(s):// 替换为 ws(s)://
  let wsBase = base.replace(/^http/, 'ws')
  if (!wsBase) {
    // dev 环境：连接到当前 host 的 ws
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    wsBase = `${proto}://${location.host}`
  }
  const token = getToken()
  const sep = path.includes('?') ? '&' : '?'
  const url = wsBase + path + (token ? `${sep}token=${token}` : '')
  return new WebSocket(url)
}
