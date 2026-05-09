<template>
  <div class="dl-view" ref="dlViewEl">

    <div class="top-bar">
      <div class="url-group">
        <input
          v-model="url"
          class="url-input"
          placeholder="粘贴视频地址… Bilibili / YouTube / Twitter 等 1000+ 网站"
          @keyup.enter="quickDownload"
          :disabled="quickDling"
        />
        <button class="btn btn-primary" @click="quickDownload" :disabled="quickDling || !url.trim()">
          {{ quickDling ? '添加中…' : '下载' }}
        </button>
        <button class="btn btn-xs" @click="onUrlEnter" :disabled="fetching || !url.trim()" title="获取视频信息，可选画质/播放列表">
          {{ fetching ? '…' : '高级' }}
        </button>
        <button class="btn" :class="{ active: showPreview }" @click="togglePreview">
          {{ showPreview ? '隐藏浏览器' : '打开浏览器' }}
        </button>
      </div>
      <div class="top-actions">
        <button class="btn" :class="{ active: activeTab === 'queue' }"    @click="activeTab = 'queue'">下载队列</button>
        <button class="btn" :class="{ active: activeTab === 'history' }"  @click="activeTab = 'history'">播放历史</button>
        <button class="btn" :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">设置</button>
      </div>
    </div>

    <div v-if="fetchError" class="error-bar">{{ fetchError }}</div>

    <div class="main-layout" ref="mainLayoutEl">

      <!-- 左侧：浏览器 / 播放器 共用区域，Tab 切换 -->
      <div v-show="showPreview" class="preview-pane" ref="previewPaneEl">

        <!-- Tab 栏 -->
        <div class="preview-tabs">
          <button
            class="preview-tab"
            :class="{ active: previewTab === 'browser' }"
            @click="switchPreviewTab('browser')"
          >浏览器</button>
          <button
            class="preview-tab"
            :class="{ active: previewTab === 'player' }"
            @click="switchPreviewTab('player')"
          >
            播放器
            <span v-if="player.filePath" class="tab-dot"></span>
          </button>
        </div>

        <!-- 浏览器面板 -->
        <template v-if="previewTab === 'browser'">
          <!-- 地址栏 -->
          <div class="browser-toolbar">
            <button class="icon-btn" @click="browserGoBack"    title="后退">&#8592;</button>
            <button class="icon-btn" @click="browserGoForward" title="前进">&#8594;</button>
            <button class="icon-btn" @click="browserReload"    title="刷新">&#8635;</button>
            <input
              v-model="browserAddressInput"
              class="address-bar"
              placeholder="输入网址或搜索…"
              @keyup.enter="browserNavigate(browserAddressInput)"
              @focus="$event.target.select()"
            />
            <button class="btn btn-xs btn-primary" @click="downloadCurrentPage" :disabled="quickDling" title="直接下载当前页面视频">
              {{ quickDling ? '添加中…' : '下载此页' }}
            </button>
          </div>

          <!-- 视频嗅探结果 -->
          <div v-if="sniffedVideos.length" class="sniff-bar">
            <span class="sniff-label">检测到视频流</span>
            <div class="sniff-list">
              <div
                v-for="(item, i) in sniffedVideos.slice(0, 5)"
                :key="i"
                class="sniff-item"
                :title="item.url"
                @click="useSniffedUrl(item.url)"
              >
                <span class="sniff-hint">{{ formatSniffHint(item.hint) }}</span>
                <span class="sniff-url">{{ truncateUrl(item.url) }}</span>
              </div>
            </div>
            <button class="btn btn-xs" @click="clearSniffed">清除</button>
          </div>

          <!-- WebContentsView 占位符：仅用于计算坐标，真实内容由 Electron 覆盖 -->
          <div class="browser-placeholder" ref="browserPlaceholderEl">
            <div v-if="!isElectron" class="browser-not-electron">
              内嵌浏览器仅在 Electron 应用中可用
            </div>
          </div>
        </template>

        <!-- 播放器面板 -->
        <div v-else class="player-panel">
          <div v-if="player.filePath" class="player-inner">
            <div class="player-top">
              <span class="player-title">{{ player.title }}</span>
              <button class="btn btn-xs" @click="closePlayer">关闭</button>
            </div>
            <video
              ref="videoEl"
              :src="player.src"
              class="player-video"
              controls
              autoplay
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onMetaLoaded"
              @ended="onEnded"
            ></video>
          </div>
          <div v-else class="empty-hint">暂无播放内容，从下载队列或播放历史中选择一个文��播放</div>
        </div>

      </div>

      <!-- 右侧操作面板 -->
      <div class="content-pane" :class="{ 'content-pane-full': !showPreview }">

        <!-- 视频信息卡 -->
        <div v-if="videoInfo" class="info-card card">
          <div class="info-top">
            <img v-if="videoInfo.thumbnail" :src="videoInfo.thumbnail" class="thumb" @error="$event.target.style.display='none'" />
            <div class="info-body">
              <div class="info-title">{{ videoInfo.title }}</div>
              <div class="info-meta">
                <span v-if="videoInfo.duration">{{ formatDuration(videoInfo.duration) }}</span>
                <span v-if="videoInfo.uploader" class="dot-sep">{{ videoInfo.uploader }}</span>
                <span v-if="videoInfo.is_playlist" class="tag">播放列表 {{ videoInfo.playlist_count }} 项</span>
                <span v-if="!videoInfo.ffmpeg_available" class="tag tag-warn">ffmpeg 未安装</span>
              </div>
            </div>
          </div>
          <div class="dl-params">
            <div class="param-row">
              <label>画质</label>
              <select v-model="selectedFormatId" class="select-input">
                <option value="">最佳质量（自动）</option>
                <option v-for="f in (videoInfo.formats || [])" :key="f.format_id" :value="f.format_id">{{ f.label }}</option>
              </select>
              <select v-if="videoInfo.is_playlist" v-model="scope" class="select-input scope-sel">
                <option value="single">仅当前视频</option>
                <option value="playlist">整个列表</option>
              </select>
            </div>
            <div class="param-row">
              <label>保存目录</label>
              <input v-model="savePath" class="path-input" placeholder="保存目录" />
              <button class="btn btn-primary" @click="addTask" :disabled="addingTask">
                {{ addingTask ? '添加中…' : '开始下载' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 下载队列 -->
        <template v-if="activeTab === 'queue'">
          <div class="panel-header">
            <span class="panel-title">下载队列</span>
            <button class="btn btn-xs" @click="clearFinished" :disabled="!finishedTasks.length">清理已完成</button>
          </div>
          <div v-if="tasks.length" class="task-list">
            <div v-for="task in tasks" :key="task.task_id" class="task-row card" @contextmenu.prevent="openTaskCtxMenu($event, task)">
              <div class="task-header">
                <span class="task-title">{{ task.title || task.url }}</span>
                <span class="status-badge" :class="statusClass(task.status)">{{ task.status }}</span>
              </div>
              <div class="task-dir">{{ task.save_dir }}</div>
              <div v-if="task.status === '等待' || task.status === '下载中'" class="prog-wrap">
                <div class="prog-bar" :style="{ width: (task.progress || 0) + '%' }"></div>
              </div>
              <div class="task-meta">
                <span v-if="task.progress > 0">{{ task.progress }}%</span>
                <span v-if="task.speed !== '-'">{{ task.speed }}</span>
                <span v-if="task.eta !== '-'">ETA {{ task.eta }}</span>
                <span class="task-fname">{{ task.filename }}</span>
              </div>
              <div class="task-foot">
                <button v-if="task.status === '等待' || task.status === '下载中'" class="btn btn-xs btn-danger" @click="cancelTask(task.task_id)">取消</button>
                <button v-if="task.status === '完成' && task.output_file" class="btn btn-xs btn-primary" @click="playFile(task.output_file)">播放</button>
                <span v-if="task.error" class="task-error">{{ task.error }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-hint">暂无下载任务</div>
        </template>

        <!-- 播放历史 -->
        <template v-if="activeTab === 'history'">
          <div class="panel-header">
            <span class="panel-title">播放历史</span>
            <button class="btn btn-xs btn-danger" @click="clearHistory" :disabled="!history.length">清空</button>
          </div>
          <div v-if="history.length" class="history-list">
            <div
              v-for="rec in history"
              :key="rec.file_path"
              class="history-row card"
              :class="{ playing: player.filePath === rec.file_path }"
              @click="playFile(rec.file_path)"
              @contextmenu.prevent="openHistoryCtxMenu($event, rec)"
            >
              <div class="hist-info">
                <div class="hist-title">{{ rec.title || rec.file_path }}</div>
                <div class="hist-meta">
                  <span>{{ formatTs(rec.last_played_ts) }}</span>
                  <span v-if="rec.play_count" class="dot-sep">{{ rec.play_count }} 次</span>
                  <span v-if="rec.duration_ms" class="dot-sep">{{ formatDuration(Math.round(rec.duration_ms / 1000)) }}</span>
                </div>
                <div class="hist-progress" v-if="rec.duration_ms && rec.last_position_ms">
                  <div class="hist-progress-bar" :style="{ width: Math.min(100, rec.last_position_ms / rec.duration_ms * 100).toFixed(1) + '%' }"></div>
                </div>
              </div>
              <button class="btn btn-xs hist-del" @click.stop="deleteHistory(rec.file_path)">删除</button>
            </div>
          </div>
          <div v-else class="empty-hint">暂无播放记录</div>
        </template>

        <!-- 设置面板 -->
        <template v-if="activeTab === 'settings' && settings">
          <div class="panel-header"><span class="panel-title">下载设置</span></div>
          <div class="settings-card card">
            <div class="setting-row">
              <label>默认保存目录</label>
              <input v-model="settings.download_dir" class="setting-input" />
            </div>
            <div class="setting-row">
              <label>并发分片数</label>
              <input v-model="settings.concurrent_fragments" type="number" min="1" max="16" class="setting-input-sm" />
              <span class="hint-text">并发数越高下载越快，但占用资源更多</span>
            </div>
            <div class="setting-row">
              <label>User-Agent</label>
              <select v-model="settings.browser_mode" class="setting-select">
                <option value="桌面">桌面浏览器（Desktop UA）</option>
                <option value="安卓">安卓浏览器（Android UA）</option>
              </select>
            </div>
            <div class="setting-row">
              <label>Bilibili vd_source</label>
              <input v-model="settings.bilibili_vd_source" class="setting-input mono" placeholder="留空使用默认值" />
            </div>
            <button class="btn btn-primary" @click="saveSettings" :disabled="savingSettings">
              {{ savingSettings ? '保存中…' : '保存设置' }}
            </button>
          </div>
        </template>

      </div>
    </div>

  </div>

  <!-- 右键菜单 -->
  <Teleport to="body">
    <template v-if="ctxMenu.show">
      <div class="ctx-backdrop" @click="closeCtxMenu" @contextmenu.prevent="closeCtxMenu"></div>
      <div
        class="ctx-menu"
        :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
      >
        <div
          v-for="item in ctxMenu.items"
          :key="item.label"
          class="ctx-item"
          :class="{ 'ctx-item-danger': item.danger }"
          @click="item.action(); closeCtxMenu()"
        >
          {{ item.label }}
        </div>
      </div>
    </template>
  </Teleport>

</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { downloadsApi } from '@/api/downloads.js'
import { playbackApi }  from '@/api/playback.js'

// ── 环境检测 ─────────────────────────────────────────────────────────────────
const isElectron = typeof window !== 'undefined' && !!window.electronAPI?.browserViewShow

// ── DOM 引用 ─────────────────────────────────────────────────────────────────
const dlViewEl           = ref(null)
const mainLayoutEl       = ref(null)
const previewPaneEl      = ref(null)
const browserPlaceholderEl = ref(null)

// ── 状态 ─────────────────────────────────────────────────────────────────────
const url              = ref('')
const fetching         = ref(false)
const fetchError       = ref('')
const videoInfo        = ref(null)
const selectedFormatId = ref('')
const scope            = ref('single')
const savePath         = ref('')
const addingTask       = ref(false)
const quickDling       = ref(false)
const showPreview      = ref(false)
const activeTab        = ref('queue')
const tasks            = ref([])
const _wsSubs          = {}
const settings         = ref(null)
const savingSettings   = ref(false)
const history          = ref([])
const videoEl          = ref(null)
const player           = ref({ filePath: '', src: '', title: '' })
let _saveTimer         = null

// 内嵌浏览器相关状态
const browserAddressInput = ref('https://www.bilibili.com/')
const sniffedVideos       = ref([])
let _stateUnsubscribe     = null
let _resizeObserver       = null

// 左侧面板 Tab：'browser' | 'player'
const previewTab = ref('browser')

// 右键菜单
const ctxMenu = ref({ show: false, x: 0, y: 0, items: [] })

function openCtxMenu(event, items) {
  // 防止菜单超出视口右侧/底部
  const vw = window.innerWidth
  const vh = window.innerHeight
  const menuW = 160
  const menuH = items.length * 36
  ctxMenu.value = {
    show: true,
    x: Math.min(event.clientX, vw - menuW - 8),
    y: Math.min(event.clientY, vh - menuH - 8),
    items,
  }
}

function closeCtxMenu() {
  ctxMenu.value.show = false
}

function openTaskCtxMenu(event, task) {
  const items = []
  if (task.status === '完成' && task.output_file) {
    items.push({ label: '播放',     action: () => playFile(task.output_file) })
    items.push({ label: '打开文件夹', action: () => openFolder(task.output_file) })
  }
  if (task.status === '等待' || task.status === '下载中') {
    items.push({ label: '取消下载', action: () => cancelTask(task.task_id), danger: true })
  }
  if (['完成', '失败', '已取消'].includes(task.status)) {
    items.push({ label: '重新下载', action: () => redownloadTask(task) })
  }
  items.push({ label: '复制链接', action: () => copyText(task.url) })
  items.push({ label: '从列表移除', action: () => removeTask(task.task_id), danger: true })
  openCtxMenu(event, items)
}

function openHistoryCtxMenu(event, rec) {
  const items = [
    { label: '播放',     action: () => playFile(rec.file_path) },
    { label: '打开文件夹', action: () => openFolder(rec.file_path) },
    { label: '复制路径', action: () => copyText(rec.file_path) },
    { label: '删除记录', action: () => deleteHistory(rec.file_path), danger: true },
  ]
  openCtxMenu(event, items)
}

function openFolder(filePath) {
  if (!filePath) return
  // Electron 环境下通过 shell.showItemInFolder
  if (window.electronAPI?.showItemInFolder) {
    window.electronAPI.showItemInFolder(filePath)
  } else {
    copyText(filePath)
  }
}

function copyText(text) {
  if (!text) return
  navigator.clipboard?.writeText(text).catch(() => {})
}

function removeTask(taskId) {
  tasks.value = tasks.value.filter(t => t.task_id !== taskId)
  if (_wsSubs[taskId]) { _wsSubs[taskId].close(); delete _wsSubs[taskId] }
}

async function redownloadTask(task) {
  if (!task.url || !task.save_dir) return
  url.value = task.url
  savePath.value = task.save_dir
  activeTab.value = 'queue'
  fetching.value = true
  fetchError.value = ''
  videoInfo.value = null
  try {
    const { task_id } = await downloadsApi.fetchInfo(task.url)
    await new Promise((resolve, reject) => {
      const ws    = downloadsApi.fetchInfoWs(task_id)
      const timer = setTimeout(() => { reject(new Error('获取超时')); ws.close() }, 60000)
      ws.onmessage = (e) => {
        clearTimeout(timer)
        const msg = JSON.parse(e.data)
        if (msg.type === 'info') { videoInfo.value = msg.data; resolve() }
        else { fetchError.value = msg.message || '获取失败'; reject(new Error(fetchError.value)) }
        ws.close()
      }
      ws.onerror = () => { clearTimeout(timer); reject(new Error('连接失败')); ws.close() }
    })
  } catch (e) {
    if (!fetchError.value) fetchError.value = e.message
  } finally {
    fetching.value = false
  }
}

// ── 计算属性 ─────────────────────────────────────────────────────────────────
const finishedTasks = computed(() =>
  tasks.value.filter(t => ['完成', '失败', '已取消'].includes(t.status))
)

// ── 工具函数 ─────────────────────────────────────────────────────────────────
function formatDuration(secs) {
  if (!secs) return ''
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatTs(ts) {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function statusClass(s) {
  return { '等待': 'badge-pending', '下载中': 'badge-info', '完成': 'badge-ok', '已取消': 'badge-off', '失败': 'badge-err' }[s] || ''
}

function truncateUrl(u) {
  try {
    const parsed = new URL(u)
    const short  = parsed.hostname + parsed.pathname
    return short.length > 60 ? short.slice(0, 60) + '…' : short
  } catch {
    return u.slice(0, 60)
  }
}

function formatSniffHint(hint) {
  if (!hint) return '视频'
  if (hint.includes('m3u8'))  return 'HLS'
  if (hint.includes('mpd'))   return 'DASH'
  if (hint.includes('mp4'))   return 'MP4'
  if (hint.includes('flv'))   return 'FLV'
  if (hint.includes('video')) return '视频流'
  return '流'
}

// ── 内嵌浏览器控制 ───────────────────────────────────────────────────────────

async function _getBrowserBounds() {
  if (!browserPlaceholderEl.value) return null
  const rect = browserPlaceholderEl.value.getBoundingClientRect()
  // BrowserWindow 的 contentView 坐标（需要考虑 devicePixelRatio）
  const dpr = window.devicePixelRatio || 1
  return {
    x:      Math.round(rect.left   * dpr),
    y:      Math.round(rect.top    * dpr),
    width:  Math.round(rect.width  * dpr),
    height: Math.round(rect.height * dpr),
  }
}

async function _showBrowserView() {
  if (!isElectron) return
  await nextTick()
  const bounds = await _getBrowserBounds()
  if (!bounds || bounds.width < 10 || bounds.height < 10) return
  await window.electronAPI.browserViewShow(bounds)
  await window.electronAPI.browserViewNavigate(browserAddressInput.value || 'https://www.bilibili.com/')
}

async function _hideBrowserView() {
  if (!isElectron) return
  await window.electronAPI.browserViewHide()
}

async function switchPreviewTab(tab) {
  previewTab.value = tab
  if (tab === 'browser') {
    // 切换到浏览器时恢复 WebContentsView
    if (showPreview.value) {
      await nextTick()
      await _showBrowserView()
      _startResizeObserver()
    }
  } else {
    // 切换到播放器时隐藏 WebContentsView（它是原生层，会遮住 video 元素）
    await _hideBrowserView()
    _stopResizeObserver()
  }
}

async function togglePreview() {
  showPreview.value = !showPreview.value
  if (showPreview.value) {
    if (previewTab.value === 'browser') {
      await _showBrowserView()
      _startResizeObserver()
    }
  } else {
    await _hideBrowserView()
    _stopResizeObserver()
  }
}

async function browserNavigate(rawUrl) {
  if (!rawUrl?.trim()) return
  let navUrl = rawUrl.trim()
  if (!/^https?:\/\//i.test(navUrl)) {
    // 不像 URL 就用搜索
    navUrl = `https://www.bing.com/search?q=${encodeURIComponent(navUrl)}`
  }
  browserAddressInput.value = navUrl
  if (isElectron) {
    await window.electronAPI.browserViewNavigate(navUrl)
  }
}

async function browserGoBack()    { if (isElectron) await window.electronAPI.browserViewGoBack() }
async function browserGoForward() { if (isElectron) await window.electronAPI.browserViewGoForward() }
async function browserReload()    { if (isElectron) await window.electronAPI.browserViewReload() }


function useSniffedUrl(sniffUrl) {
  url.value = sniffUrl
}

async function clearSniffed() {
  sniffedVideos.value = []
  if (isElectron) await window.electronAPI.browserViewClearSniffed()
}

// ── ResizeObserver：跟随占位符大小自动调整 WebContentsView ──────────────────

function _startResizeObserver() {
  if (!isElectron || !browserPlaceholderEl.value) return
  _resizeObserver = new ResizeObserver(async () => {
    if (!showPreview.value) return
    const bounds = await _getBrowserBounds()
    if (bounds && bounds.width > 10 && bounds.height > 10) {
      await window.electronAPI.browserViewResize(bounds)
    }
  })
  _resizeObserver.observe(browserPlaceholderEl.value)
  // 也监听整个 view，防止窗口 resize 时坐标偏移
  if (dlViewEl.value) _resizeObserver.observe(dlViewEl.value)
}

function _stopResizeObserver() {
  if (_resizeObserver) {
    _resizeObserver.disconnect()
    _resizeObserver = null
  }
}

// ── 状态订阅（主进程推送 URL 变化和嗅探结果）────────────────────────────────

function _subscribeState() {
  if (!isElectron) return
  _stateUnsubscribe = window.electronAPI.onBrowserViewState((state) => {
    if (state.url) browserAddressInput.value = state.url
    if (Array.isArray(state.sniffed)) sniffedVideos.value = state.sniffed
  })
}

// ── 下载相关逻辑 ─────────────────────────────────────────────────────────────

async function onUrlEnter() {
  if (!url.value.trim()) return
  fetching.value   = true
  fetchError.value = ''
  videoInfo.value  = null
  selectedFormatId.value = ''
  // 如果浏览器面板已打开，同步跳转
  if (showPreview.value) {
    browserAddressInput.value = url.value.trim()
    if (isElectron) await window.electronAPI.browserViewNavigate(url.value.trim())
  }
  try {
    const { task_id } = await downloadsApi.fetchInfo(url.value.trim())
    await new Promise((resolve, reject) => {
      const ws    = downloadsApi.fetchInfoWs(task_id)
      const timer = setTimeout(() => { reject(new Error('获取超时')); ws.close() }, 60000)
      ws.onmessage = (e) => {
        clearTimeout(timer)
        const msg = JSON.parse(e.data)
        if (msg.type === 'info') {
          videoInfo.value = msg.data
          if (!savePath.value && settings.value?.download_dir) savePath.value = settings.value.download_dir
          resolve()
        } else {
          fetchError.value = msg.message || '获取失败'
          reject(new Error(fetchError.value))
        }
        ws.close()
      }
      ws.onerror = () => { clearTimeout(timer); reject(new Error('WebSocket 连接失败')); ws.close() }
    })
  } catch (e) {
    if (!fetchError.value) fetchError.value = e.message
  } finally {
    fetching.value = false
  }
}

// 订阅下载进度 WebSocket，更新 tasks 列表
function _subscribeTask(task_id) {
  const ws = downloadsApi.taskWs(task_id)
  _wsSubs[task_id] = ws
  ws.onmessage = (e) => {
    const msg  = JSON.parse(e.data)
    const task = tasks.value.find(t => t.task_id === task_id)
    if (!task) return
    if (msg.type === 'progress') {
      task.status   = '下载中'
      task.progress = msg.progress ?? task.progress
      task.speed    = msg.speed    ?? task.speed
      task.eta      = msg.eta      ?? task.eta
      task.filename = msg.filename  || task.filename
    } else if (msg.type === 'done') {
      task.status = '完成'; task.progress = 100
      if (msg.output_file) task.output_file = msg.output_file
      delete _wsSubs[task_id]; ws.close()
    } else if (msg.type === 'error') {
      task.status = msg.status || '失败'; task.error = msg.message
      delete _wsSubs[task_id]; ws.close()
    }
  }
  ws.onerror = () => {
    const task = tasks.value.find(t => t.task_id === task_id)
    if (task && task.status !== '完成') { task.status = '失败'; task.error = 'WebSocket 断开' }
  }
}

// 直接下载（无需获取信息，使用最佳画质+默认目录）
async function quickDownload(targetUrl) {
  const dlUrl = (typeof targetUrl === 'string' ? targetUrl : url.value).trim()
  if (!dlUrl) return
  const dir = savePath.value.trim() || settings.value?.download_dir || ''
  if (!dir) { fetchError.value = '请先在设置中配置默认保存目录'; return }
  quickDling.value = true
  fetchError.value = ''
  try {
    const fragments = parseInt(settings.value?.concurrent_fragments || '8', 10)
    const { task_id } = await downloadsApi.createTask({
      url: dlUrl, format_id: 'bestvideo+bestaudio/best',
      save_path: dir, scope: 'single', concurrent_fragments: fragments,
    })
    tasks.value.push({
      task_id, url: dlUrl, title: dlUrl,
      status: '等待', progress: 0, speed: '-', eta: '-',
      save_dir: dir, error: '', filename: '', output_file: '',
    })
    activeTab.value = 'queue'
    _subscribeTask(task_id)
    url.value = ''
  } catch (e) {
    fetchError.value = e.message
  } finally {
    quickDling.value = false
  }
}

// 浏览器工具栏：下载当前浏览器页面
async function downloadCurrentPage() {
  const pageUrl = browserAddressInput.value?.trim()
  if (!pageUrl) return
  await quickDownload(pageUrl)
}

async function addTask() {
  if (!savePath.value.trim() || !videoInfo.value) return
  addingTask.value = true
  const formatId  = selectedFormatId.value || 'bestvideo+bestaudio/best'
  const fragments = parseInt(settings.value?.concurrent_fragments || '8', 10)
  try {
    const { task_id } = await downloadsApi.createTask({
      url: url.value.trim(), format_id: formatId,
      save_path: savePath.value.trim(), scope: scope.value,
      concurrent_fragments: fragments,
    })
    tasks.value.push({
      task_id, url: url.value.trim(), title: videoInfo.value.title,
      status: '等待', progress: 0, speed: '-', eta: '-',
      save_dir: savePath.value.trim(), error: '', filename: '', output_file: '',
    })
    activeTab.value = 'queue'
    _subscribeTask(task_id)
    url.value = ''; videoInfo.value = null
  } catch (e) {
    fetchError.value = e.message
  } finally {
    addingTask.value = false
  }
}

async function cancelTask(taskId) {
  try {
    await downloadsApi.cancelTask(taskId)
    const task = tasks.value.find(t => t.task_id === taskId)
    if (task) task.status = '已取消'
    if (_wsSubs[taskId]) { _wsSubs[taskId].close(); delete _wsSubs[taskId] }
  } catch {}
}

async function clearFinished() {
  try {
    await downloadsApi.clearFinished()
    tasks.value = tasks.value.filter(t => !['完成', '失败', '已取消'].includes(t.status))
  } catch {}
}

async function saveSettings() {
  savingSettings.value = true
  try { await downloadsApi.updateSettings(settings.value) } catch {}
  finally { savingSettings.value = false }
}

async function loadHistory() {
  try { history.value = await playbackApi.list() } catch {}
}

async function deleteHistory(filePath) {
  try {
    await playbackApi.deleteOne(filePath)
    history.value = history.value.filter(r => r.file_path !== filePath)
  } catch {}
}

async function clearHistory() {
  if (!confirm('确定清空所有播放记录？')) return
  try { await playbackApi.clearAll(); history.value = [] } catch {}
}

async function playFile(filePath) {
  if (!filePath) return
  const token = window.__TOOLPACK_TOKEN__ || ''
  const base  = window.__TOOLPACK_API_BASE__ || ''
  const qs    = new URLSearchParams({ path: filePath })
  if (token) qs.set('token', token)
  player.value = { filePath, src: `${base}/api/files/serve?${qs}`, title: filePath.split(/[\/\\]/).pop() }
  playbackApi.update(filePath, { play_count: 1, title: player.value.title }).catch(() => {})
  // 自动打开左侧面板并切换到播放器 tab
  if (!showPreview.value) {
    showPreview.value = true
  }
  await switchPreviewTab('player')
}

function closePlayer() {
  if (videoEl.value) videoEl.value.pause()
  _persistPosition()
  player.value = { filePath: '', src: '', title: '' }
}

function onTimeUpdate() {
  clearTimeout(_saveTimer)
  _saveTimer = setTimeout(_persistPosition, 5000)
}

function onMetaLoaded() {
  if (!videoEl.value) return
  const rec = history.value.find(r => r.file_path === player.value.filePath)
  if (rec?.last_position_ms) videoEl.value.currentTime = rec.last_position_ms / 1000
  const dur = Math.round(videoEl.value.duration * 1000)
  playbackApi.update(player.value.filePath, { duration_ms: dur }).catch(() => {})
}

function onEnded() { _persistPosition() }

function _persistPosition() {
  if (!videoEl.value || !player.value.filePath) return
  const posMs = Math.round(videoEl.value.currentTime * 1000)
  playbackApi.update(player.value.filePath, { last_position_ms: posMs }).catch(() => {})
  const rec = history.value.find(r => r.file_path === player.value.filePath)
  if (rec) rec.last_position_ms = posMs
}

// ── 生命周期 ─────────────────────────────────────────────────────────────────

async function loadTasks() {
  try {
    const list = await downloadsApi.listTasks()
    // 恢复历史任务，补齐前端需要的字段
    tasks.value = list.map(t => ({
      speed: '-', eta: '-',
      ...t,
    }))
  } catch {}
}

onMounted(async () => {
  try { settings.value = await downloadsApi.getSettings() } catch {}
  await Promise.all([loadHistory(), loadTasks()])
  _subscribeState()
})

onBeforeUnmount(async () => {
  clearTimeout(_saveTimer)
  Object.values(_wsSubs).forEach(ws => ws.close())
  _stopResizeObserver()
  if (_stateUnsubscribe) _stateUnsubscribe()
  // 离开页面时隐藏浏览器面板
  if (showPreview.value) await _hideBrowserView()
})
</script>

<style scoped>
.dl-view { display: flex; flex-direction: column; overflow: hidden; padding: 14px 18px 0; height: 100%; }

.top-bar { display: flex; align-items: center; gap: 10px; padding: 0 0 14px; flex-shrink: 0; flex-wrap: wrap; }
.url-group { display: flex; gap: 8px; flex: 1; min-width: 300px; }
.url-input {
  flex: 1; padding: 8px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 13px;
}
.url-input:focus { outline: none; border-color: var(--accent); }
.top-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

.error-bar {
  padding: 9px 14px; margin-bottom: 12px; flex-shrink: 0;
  background: rgba(224,84,84,.1); border: 1px solid rgba(224,84,84,.3);
  border-radius: var(--radius-sm); font-size: 12px; color: var(--danger);
}

.main-layout { display: flex; gap: 0; flex: 1; overflow: hidden; min-height: 0; }

/* ── 预览区 ── */
.preview-pane {
  display: flex; flex-direction: column; flex: 1; min-width: 0;
  border-right: 1px solid var(--border); overflow: hidden;
  background: var(--bg-card);
}

/* 地址栏 */
.browser-toolbar {
  display: flex; align-items: center; gap: 6px; padding: 6px 8px;
  border-bottom: 1px solid var(--border); flex-shrink: 0;
  background: var(--bg-surface);
}
.icon-btn {
  padding: 4px 8px; background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 13px;
  cursor: pointer; line-height: 1;
}
.icon-btn:hover { border-color: var(--accent); color: var(--accent); }
.address-bar {
  flex: 1; padding: 5px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 12px;
}
.address-bar:focus { outline: none; border-color: var(--accent); }

/* 嗅探结果条 */
.sniff-bar {
  display: flex; align-items: center; gap: 8px; padding: 5px 10px;
  border-bottom: 1px solid var(--border); background: rgba(232,115,10,.06);
  flex-shrink: 0; flex-wrap: wrap;
}
.sniff-label { font-size: 11px; font-weight: 700; color: var(--accent); flex-shrink: 0; }
.sniff-list { display: flex; gap: 6px; flex-wrap: wrap; flex: 1; }
.sniff-item {
  display: flex; align-items: center; gap: 5px; padding: 2px 8px;
  background: var(--accent-dim); border: 1px solid var(--accent); border-radius: 2px;
  cursor: pointer; font-size: 11px; max-width: 260px;
  transition: background .15s;
}
.sniff-item:hover { background: var(--accent); color: #fff; }
.sniff-hint { font-weight: 700; flex-shrink: 0; color: var(--accent); }
.sniff-item:hover .sniff-hint { color: #fff; }
.sniff-url { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-secondary); }
.sniff-item:hover .sniff-url { color: rgba(255,255,255,.85); }

/* WebContentsView 占位符 */
.browser-placeholder {
  flex: 1; position: relative; background: var(--bg-surface); overflow: hidden;
}
.browser-not-electron {
  display: flex; align-items: center; justify-content: center; height: 100%;
  color: var(--text-dimmed); font-size: 13px;
}

/* ── 右侧操作面板 ── */
.content-pane { width: 340px; flex-shrink: 0; overflow-y: auto; padding: 12px; min-width: 0; border-left: 1px solid var(--border); background: var(--bg-surface); }
.content-pane-full { width: 100%; flex: 1; border-left: none; }

.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px; margin-bottom: 12px; }

.info-top { display: flex; gap: 12px; margin-bottom: 12px; }
.thumb { width: 140px; height: 79px; object-fit: cover; border-radius: var(--radius-sm); flex-shrink: 0; background: var(--bg-hover); }
.info-body { flex: 1; min-width: 0; }
.info-title { font-weight: 600; font-size: 13px; color: var(--text-primary); line-height: 1.4; margin-bottom: 6px; }
.info-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 11px; color: var(--text-secondary); }
.dot-sep::before { content: '·'; margin-right: 8px; opacity: .4; }
.tag { padding: 1px 7px; background: var(--accent-dim); color: var(--accent); border-radius: 2px; font-size: 10px; font-weight: 700; letter-spacing: .3px; }
.tag-warn { background: rgba(212,160,23,.12); color: var(--warning); }

.dl-params { display: flex; flex-direction: column; gap: 8px; }
.param-row { display: flex; align-items: center; gap: 8px; }
.param-row label { width: 60px; font-size: 12px; color: var(--text-secondary); flex-shrink: 0; }
.select-input {
  flex: 1; padding: 6px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 12px;
}
.scope-sel { flex: 0 0 130px; }
.path-input {
  flex: 1; padding: 6px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 12px;
}
.path-input:focus { outline: none; border-color: var(--accent); }

.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.panel-title { font-size: 12px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .5px; }

.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-row { padding: 10px 14px; }
.task-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 2px; }
.task-title  { font-size: 12px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-dir    { font-size: 10px; color: var(--text-dimmed); margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prog-wrap   { height: 3px; background: var(--bg-hover); border-radius: 2px; margin-bottom: 6px; overflow: hidden; }
.prog-bar    { height: 100%; background: var(--accent); transition: width 0.4s; }
.task-meta   { display: flex; gap: 8px; font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-variant-numeric: tabular-nums; }
.task-fname  { color: var(--text-dimmed); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 250px; }
.task-foot   { display: flex; align-items: center; gap: 8px; }
.task-error  { font-size: 10px; color: var(--danger); }

.status-badge { font-size: 10px; padding: 1px 7px; border-radius: 2px; font-weight: 700; flex-shrink: 0; letter-spacing: .3px; }
.badge-info    { background: rgba(74,144,217,.12); color: var(--info); }
.badge-ok      { background: rgba(58,171,82,.12);  color: var(--success); }
.badge-err     { background: rgba(224,84,84,.12);  color: var(--danger); }
.badge-off     { background: rgba(78,80,88,.15);   color: var(--text-dimmed); }
.badge-pending { background: rgba(212,160,23,.12); color: var(--warning); }

.history-list { display: flex; flex-direction: column; gap: 6px; }
.history-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  cursor: pointer; transition: border-color .15s, background .15s;
}
.history-row:hover   { border-color: var(--accent); background: var(--bg-hover); }
.history-row.playing { border-color: var(--accent); background: var(--accent-dim); }
.hist-info { flex: 1; min-width: 0; }
.hist-title { font-size: 12px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hist-meta  { font-size: 10px; color: var(--text-secondary); margin-top: 2px; }
.hist-progress { height: 2px; background: var(--bg-hover); border-radius: 1px; margin-top: 5px; overflow: hidden; }
.hist-progress-bar { height: 100%; background: var(--accent); }
.hist-del { opacity: 0; transition: opacity .15s; flex-shrink: 0; }
.history-row:hover .hist-del { opacity: 1; }

.settings-card { display: flex; flex-direction: column; gap: 12px; }
.setting-row { display: flex; align-items: center; gap: 12px; font-size: 12px; }
.setting-row label { width: 120px; color: var(--text-secondary); flex-shrink: 0; }
.setting-input {
  flex: 1; padding: 6px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 12px;
}
.setting-input:focus { outline: none; border-color: var(--accent); }
.setting-input-sm { width: 70px; padding: 6px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 12px; }
.setting-select {
  flex: 1; padding: 6px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); font-size: 12px;
}
.setting-input.mono { font-family: monospace; font-size: 11px; }
.hint-text { font-size: 11px; color: var(--text-dimmed); }

/* ── Tab 切换栏 ── */
.preview-tabs {
  display: flex; gap: 0; flex-shrink: 0;
  border-bottom: 1px solid var(--border); background: var(--bg-surface);
}
.preview-tab {
  position: relative; padding: 7px 18px; font-size: 12px; font-weight: 600;
  color: var(--text-secondary); background: none; border: none;
  border-bottom: 2px solid transparent; cursor: pointer;
  transition: color .15s, border-color .15s;
  display: flex; align-items: center; gap: 5px;
}
.preview-tab:hover { color: var(--text-primary); }
.preview-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent); flex-shrink: 0;
}

/* ── 播放器面板 ── */
.player-panel {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  background: var(--bg-card);
}
.player-inner {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}
.player-top {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; gap: 10px; flex-shrink: 0;
  border-bottom: 1px solid var(--border);
}
.player-title { font-size: 12px; color: var(--text-primary); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.player-video { flex: 1; width: 100%; min-height: 0; background: #000; border-radius: 0; display: block; object-fit: contain; }

.empty-hint { text-align: center; padding: 32px; color: var(--text-dimmed); font-size: 13px; }

/* ── 右键菜单 ── */
.ctx-backdrop {
  position: fixed; inset: 0; z-index: 9998;
}
.ctx-menu {
  position: fixed; z-index: 9999;
  min-width: 140px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 6px 20px rgba(0,0,0,.35);
  padding: 4px 0;
  overflow: hidden;
}
.ctx-item {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  white-space: nowrap;
  transition: background .1s;
}
.ctx-item:hover { background: var(--bg-hover); }
.ctx-item-danger { color: var(--danger); }
.ctx-item-danger:hover { background: rgba(224,84,84,.1); }
</style>
