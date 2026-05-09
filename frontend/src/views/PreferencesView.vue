<template>
  <div class="prefs-view">
    <div class="page-header">
      <div>
        <h2>偏好设置</h2>
        <p class="page-desc">系统信息与全局配置</p>
      </div>
      <button class="btn" @click="refresh" :disabled="loading">刷新</button>
    </div>

    <div v-if="loading" class="loading-hint">加载中…</div>
    <div v-if="error" class="error-bar">{{ error }}</div>

    <!-- 系统信息 -->
    <section class="section card" v-if="info">
      <h3>系统信息</h3>
      <div class="info-grid">
        <div class="info-row">
          <span class="info-label">操作系统</span>
          <span class="info-val">{{ info.os }} {{ info.os_version }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Python 版本</span>
          <span class="info-val mono">{{ info.python_version }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">管理员权限</span>
          <span class="info-val" :class="info.is_admin ? 'text-ok' : 'text-warn'">
            {{ info.is_admin ? '是' : '否（部分功能受限）' }}
          </span>
        </div>
      </div>
      <button v-if="!info.is_admin" class="btn btn-sm btn-primary" @click="elevate" style="margin-top:12px;">
        以管理员身份重启
      </button>
    </section>

    <!-- 开机自启 -->
    <section class="section card" v-if="info">
      <h3>开机自启</h3>
      <div class="toggle-row">
        <div class="toggle-info">
          <div class="toggle-title">开机时自动启动工具箱</div>
          <div class="toggle-desc">程序将在登录后自动启动并最小化到系统托盘</div>
        </div>
        <label class="toggle">
          <input type="checkbox" :checked="info.autostart_enabled" @change="toggleAutostart" />
          <span class="toggle-slider"></span>
        </label>
      </div>
    </section>

    <!-- ffmpeg 状态 -->
    <section class="section card">
      <h3>ffmpeg</h3>
      <div v-if="ffmpegStatus">
        <div class="info-row">
          <span class="info-label">状态</span>
          <span class="info-val" :class="ffmpegStatus.installed ? 'text-ok' : 'text-warn'">
            {{ ffmpegStatus.installed ? '已安装' : '未安装' }}
          </span>
        </div>
        <div v-if="ffmpegStatus.installed" class="info-row">
          <span class="info-label">路径</span>
          <span class="info-val mono small">{{ ffmpegStatus.path }}</span>
        </div>
        <div v-if="ffmpegStatus.version" class="info-row">
          <span class="info-label">版本</span>
          <span class="info-val mono small">{{ ffmpegStatus.version }}</span>
        </div>
      </div>

      <div v-if="!ffmpegStatus?.installed" style="margin-top:12px;">
        <button class="btn btn-primary" @click="installFfmpeg" :disabled="installingFfmpeg">
          {{ installingFfmpeg ? '安装中…' : '自动安装 ffmpeg' }}
        </button>
        <div v-if="ffmpegInstallLog.length" class="install-log">
          <div v-for="(line, i) in ffmpegInstallLog" :key="i" class="log-line">{{ line }}</div>
        </div>
      </div>
    </section>

    <!-- 下载设置 -->
    <section class="section card" v-if="dlSettings">
      <h3>下载设置</h3>
      <div class="form-rows">
        <div class="form-row">
          <label>默认保存路径</label>
          <input v-model="dlSettings.download_dir" class="form-input" />
        </div>
        <div class="form-row">
          <label>并发分片数</label>
          <input v-model="dlSettings.concurrent_fragments" type="number" min="1" max="16" class="form-input-sm" />
        </div>
        <div class="form-row">
          <label>浏览器模式</label>
          <select v-model="dlSettings.browser_mode" class="form-select">
            <option value="桌面">桌面（Desktop UA）</option>
            <option value="安卓">安卓（Android UA）</option>
          </select>
        </div>
        <div class="form-row">
          <label>Bilibili vd_source</label>
          <input v-model="dlSettings.bilibili_vd_source" class="form-input" placeholder="可选，用于 B 站视频下载" />
        </div>
      </div>
      <button class="btn btn-primary" @click="saveDlSettings" :disabled="savingDl">
        {{ savingDl ? '保存中…' : '保存下载设置' }}
      </button>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useSystemStore } from '@/stores/system.js'
import { storeToRefs } from 'pinia'
import { ffmpegApi } from '@/api/ffmpeg.js'
import { downloadsApi } from '@/api/downloads.js'

const systemStore = useSystemStore()
const { info, loading, error } = storeToRefs(systemStore)

const ffmpegStatus      = ref(null)
const installingFfmpeg  = ref(false)
const ffmpegInstallLog  = ref([])

const dlSettings = ref(null)
const savingDl   = ref(false)

async function refresh() {
  await systemStore.fetchInfo()
  await loadFfmpeg()
}

async function loadFfmpeg() {
  try { ffmpegStatus.value = await ffmpegApi.status() } catch {}
}

async function installFfmpeg() {
  installingFfmpeg.value = true
  ffmpegInstallLog.value = []
  try {
    const { task_id } = await ffmpegApi.install()
    const ws = ffmpegApi.installWs(task_id)
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'progress') ffmpegInstallLog.value.push(msg.message)
      if (msg.type === 'done') { installingFfmpeg.value = false; loadFfmpeg(); ws.close() }
      if (msg.type === 'error') { ffmpegInstallLog.value.push('错误：' + msg.message); installingFfmpeg.value = false; ws.close() }
    }
    ws.onerror = () => { installingFfmpeg.value = false }
  } catch (e) {
    ffmpegInstallLog.value.push('启动失败：' + e.message)
    installingFfmpeg.value = false
  }
}

async function toggleAutostart(e) {
  await systemStore.setAutostart(e.target.checked)
}

async function elevate() {
  try { await systemStore.elevate() } catch {}
}

async function saveDlSettings() {
  savingDl.value = true
  try { await downloadsApi.updateSettings(dlSettings.value) }
  catch {}
  finally { savingDl.value = false }
}

onMounted(async () => {
  await systemStore.fetchInfo()
  await loadFfmpeg()
  try { dlSettings.value = await downloadsApi.getSettings() } catch {}
})
</script>

<style scoped>
.prefs-view { width: 100%; max-width: 700px; margin: 0 auto; padding: 24px; overflow-y: auto; box-sizing: border-box; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; color: var(--text-primary); }
.page-desc { font-size: 12px; color: var(--text-secondary); margin: 0; }

.loading-hint { text-align: center; padding: 20px; color: var(--text-dimmed); }
.error-bar { padding: 10px 16px; margin-bottom: 16px; background: rgba(250,82,82,.1); border: 1px solid rgba(250,82,82,.3); border-radius: var(--radius-sm); font-size: 13px; color: var(--danger); }

.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; margin-bottom: 16px; }
.section h3 { margin: 0 0 16px; font-size: 15px; color: var(--text-primary); }

.info-grid { display: flex; flex-direction: column; gap: 10px; }
.info-row { display: flex; align-items: center; gap: 16px; font-size: 13px; }
.info-label { width: 110px; color: var(--text-secondary); flex-shrink: 0; }
.info-val { color: var(--text-primary); }
.mono { font-family: monospace; font-size: 12px; }
.small { font-size: 11px; }
.text-ok   { color: var(--success); }
.text-warn { color: var(--warning); }

.toggle-row { display: flex; align-items: center; gap: 16px; }
.toggle-info { flex: 1; }
.toggle-title { font-size: 14px; color: var(--text-primary); margin-bottom: 3px; }
.toggle-desc  { font-size: 12px; color: var(--text-secondary); }
.toggle { position: relative; display: inline-block; width: 44px; height: 24px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; cursor: pointer; inset: 0;
  background: var(--border); border-radius: 12px; transition: 0.25s;
}
.toggle-slider::before {
  content: ''; position: absolute; height: 18px; width: 18px; left: 3px; bottom: 3px;
  background: white; border-radius: 50%; transition: 0.25s;
}
.toggle input:checked + .toggle-slider { background: var(--accent); }
.toggle input:checked + .toggle-slider::before { transform: translateX(20px); }

.install-log {
  margin-top: 10px; padding: 10px; background: var(--bg-surface);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  max-height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; color: var(--text-secondary);
}
.log-line { margin: 2px 0; }

.form-rows { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }
.form-row { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.form-row label { width: 110px; color: var(--text-secondary); flex-shrink: 0; }
.form-input {
  flex: 1; padding: 7px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 13px;
}
.form-input:focus { outline: none; border-color: var(--accent); }
.form-input-sm { width: 80px; padding: 7px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); }
.form-select {
  flex: 1; padding: 7px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 13px; cursor: pointer;
}
</style>
