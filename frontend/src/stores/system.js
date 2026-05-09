import { defineStore } from 'pinia'
import { ref } from 'vue'
import { systemApi } from '@/api/system.js'

export const useSystemStore = defineStore('system', () => {
  const info = ref(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchInfo() {
    loading.value = true
    error.value = ''
    try {
      info.value = await systemApi.getInfo()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function setAutostart(enabled) {
    try {
      if (enabled) {
        await systemApi.enableAutostart()
      } else {
        await systemApi.disableAutostart()
      }
      if (info.value) info.value.autostart_enabled = enabled
    } catch (e) {
      error.value = e.message
    }
  }

  async function elevate() {
    try {
      await systemApi.elevate()
    } catch (e) {
      error.value = e.message
    }
  }

  return { info, loading, error, fetchInfo, setAutostart, elevate }
})
