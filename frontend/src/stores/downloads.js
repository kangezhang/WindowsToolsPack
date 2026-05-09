import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { downloadsApi } from '@/api/downloads.js'

export const useDownloadStore = defineStore('downloads', () => {
  const tasks = ref([])          // { task_id, title, status, progress, speed, eta, save_path, error }
  const settings = ref(null)
  const fetchInfoResult = ref(null)
  const fetchInfoLoading = ref(false)
  const fetchInfoError = ref('')

  // WebSocket subscriptions keyed by task_id
  const _wsSubs = {}

  const activeTasks = computed(() => tasks.value.filter(t => t.status === 'downloading'))
  const finishedTasks = computed(() => tasks.value.filter(t => ['done', 'cancelled', 'error'].includes(t.status)))

  function _upsertTask(taskId, patch) {
    const idx = tasks.value.findIndex(t => t.task_id === taskId)
    if (idx >= 0) {
      tasks.value[idx] = { ...tasks.value[idx], ...patch }
    } else {
      tasks.value.push({ task_id: taskId, status: 'pending', progress: 0, ...patch })
    }
  }

  async function fetchVideoInfo(url) {
    fetchInfoLoading.value = true
    fetchInfoError.value = ''
    fetchInfoResult.value = null
    try {
      const { task_id } = await downloadsApi.fetchInfo(url)
      return new Promise((resolve, reject) => {
        const ws = downloadsApi.fetchInfoWs(task_id)
        ws.onmessage = (e) => {
          const msg = JSON.parse(e.data)
          if (msg.type === 'info') {
            fetchInfoResult.value = msg.data
            resolve(msg.data)
          } else if (msg.type === 'error') {
            fetchInfoError.value = msg.message
            reject(new Error(msg.message))
          }
          ws.close()
        }
        ws.onerror = () => { reject(new Error('WebSocket 错误')); ws.close() }
      })
    } catch (e) {
      fetchInfoError.value = e.message
      throw e
    } finally {
      fetchInfoLoading.value = false
    }
  }

  async function addTask(payload) {
    const { task_id } = await downloadsApi.createTask(payload)
    _upsertTask(task_id, { title: payload.title || '未知', status: 'downloading', save_path: payload.save_path })

    const ws = downloadsApi.taskWs(task_id)
    _wsSubs[task_id] = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'progress') {
        _upsertTask(task_id, { status: 'downloading', progress: msg.progress, speed: msg.speed, eta: msg.eta, title: msg.title || undefined })
      } else if (msg.type === 'done') {
        _upsertTask(task_id, { status: 'done', progress: 100 })
        delete _wsSubs[task_id]
      } else if (msg.type === 'error') {
        _upsertTask(task_id, { status: 'error', error: msg.message })
        delete _wsSubs[task_id]
      }
    }
    ws.onerror = () => {
      _upsertTask(task_id, { status: 'error', error: 'WebSocket 断开' })
    }

    return task_id
  }

  async function cancelTask(taskId) {
    await downloadsApi.cancelTask(taskId)
    _upsertTask(taskId, { status: 'cancelled' })
    if (_wsSubs[taskId]) {
      _wsSubs[taskId].close()
      delete _wsSubs[taskId]
    }
  }

  async function clearFinished() {
    await downloadsApi.clearFinished()
    tasks.value = tasks.value.filter(t => !['done', 'cancelled', 'error'].includes(t.status))
  }

  async function loadSettings() {
    settings.value = await downloadsApi.getSettings()
  }

  async function saveSettings(payload) {
    settings.value = await downloadsApi.updateSettings(payload)
  }

  return {
    tasks, settings, fetchInfoResult, fetchInfoLoading, fetchInfoError,
    activeTasks, finishedTasks,
    fetchVideoInfo, addTask, cancelTask, clearFinished,
    loadSettings, saveSettings,
  }
})
