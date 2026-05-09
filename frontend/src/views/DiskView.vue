<template>
  <div class="disk-view">
    <div class="page-header">
      <div>
        <h2>磁盘可视化</h2>
        <p class="page-desc">扫描目录，按大小可视化文件占用</p>
      </div>
    </div>

    <!-- 路径输入 -->
    <div class="path-row">
      <input
        v-model="scanPath"
        class="path-input"
        placeholder="输入要扫描的目录，例如 C:\Users"
        @keyup.enter="startScan"
      />
      <button class="btn btn-primary" @click="startScan" :disabled="scanning">
        {{ scanning ? '扫描中…' : '扫描' }}
      </button>
    </div>

    <div v-if="error" class="error-bar">{{ error }}</div>

    <!-- 面包屑导航 -->
    <div v-if="breadcrumbs.length" class="breadcrumbs">
      <span
        v-for="(crumb, i) in breadcrumbs"
        :key="i"
        class="crumb"
        :class="{ last: i === breadcrumbs.length - 1 }"
        @click="i < breadcrumbs.length - 1 && navigateTo(crumb)"
      >{{ crumb.name }}</span>
    </div>

    <!-- 进度条 -->
    <div v-if="scanning" class="progress-bar-wrap">
      <div class="progress-bar-inner" :style="{ width: scanProgress + '%' }"></div>
      <span class="progress-text">{{ scanStatus }}</span>
    </div>

    <!-- 可视化条形图 -->
    <div v-if="currentItems.length" class="viz-list">
      <div class="viz-header">
        <span>名称</span>
        <span>大小</span>
        <span>占比</span>
      </div>
      <div
        v-for="item in currentItems"
        :key="item.path"
        class="viz-row"
        :class="{ dir: item.type === 'dir' }"
        @click="item.type === 'dir' && drillDown(item)"
        :title="item.path"
      >
        <span class="viz-icon" :class="item.type === 'dir' ? 'icon-dir' : 'icon-file'"></span>
        <span class="viz-name">{{ item.name }}</span>
        <span class="viz-size">{{ formatBytes(item.size) }}</span>
        <div class="viz-bar-wrap">
          <div class="viz-bar" :style="{ width: item.percentage + '%', background: barColor(item.percentage) }"></div>
          <span class="viz-pct">{{ item.percentage.toFixed(1) }}%</span>
        </div>
      </div>
    </div>

    <div v-else-if="!scanning && scanned" class="empty-hint">该目录为空</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { diskApi } from '@/api/disk.js'

const scanPath   = ref('C:\\Users')
const scanning   = ref(false)
const scanned    = ref(false)
const error      = ref('')
const scanProgress = ref(0)
const scanStatus   = ref('')

// 树形导航栈：每个元素 { name, items }
const navStack = ref([])

const currentItems = computed(() => {
  if (!navStack.value.length) return []
  return navStack.value[navStack.value.length - 1].items
})

const breadcrumbs = computed(() => navStack.value.map(n => n))

function drillDown(item) {
  navStack.value.push({ name: item.name, path: item.path, items: item.children || [] })
}

function navigateTo(crumb) {
  const idx = navStack.value.indexOf(crumb)
  if (idx >= 0) navStack.value = navStack.value.slice(0, idx + 1)
}

async function startScan() {
  if (!scanPath.value.trim()) return
  scanning.value = true
  scanned.value  = false
  error.value    = ''
  scanProgress.value = 0
  scanStatus.value   = '正在扫描…'
  navStack.value = []

  try {
    const { task_id } = await diskApi.startScan(scanPath.value.trim())
    const ws = diskApi.openWs(task_id)

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'progress') {
        const total = msg.total || 1
        scanProgress.value = Math.round((msg.scanned || 0) / total * 100)
        scanStatus.value   = `已扫描 ${msg.scanned || 0} / ${total} 项`
      } else if (msg.type === 'done') {
        navStack.value = [{ name: scanPath.value, path: scanPath.value, items: msg.items || [] }]
        scanProgress.value = 100
        scanning.value = false
        scanned.value  = true
        ws.close()
      } else if (msg.type === 'error') {
        error.value    = msg.message
        scanning.value = false
        ws.close()
      }
    }
    ws.onerror = () => {
      error.value    = 'WebSocket 连接失败'
      scanning.value = false
    }
  } catch (e) {
    error.value    = e.message
    scanning.value = false
  }
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = bytes, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(1)} ${units[i]}`
}

function barColor(pct) {
  if (pct > 50) return '#fa5252'
  if (pct > 20) return '#ff922b'
  if (pct > 10) return '#fcc419'
  return '#51cf66'
}
</script>

<style scoped>
.disk-view { width: 100%; max-width: 900px; margin: 0 auto; padding: 24px; overflow-y: auto; box-sizing: border-box; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; color: var(--text-primary); }
.page-desc { font-size: 12px; color: var(--text-secondary); margin: 0; }

.path-row { display: flex; gap: 10px; margin-bottom: 16px; }
.path-input {
  flex: 1; padding: 9px 14px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px; font-family: monospace;
}
.path-input:focus { outline: none; border-color: var(--accent); }

.error-bar {
  padding: 10px 16px; margin-bottom: 16px;
  background: rgba(250,82,82,.1); border: 1px solid rgba(250,82,82,.3);
  border-radius: var(--radius-sm); font-size: 13px; color: var(--danger);
}

.breadcrumbs { display: flex; gap: 4px; margin-bottom: 12px; font-size: 13px; flex-wrap: wrap; }
.crumb {
  color: var(--accent); cursor: pointer;
  padding: 2px 4px; border-radius: 3px;
}
.crumb:hover { background: rgba(34,139,230,.1); }
.crumb.last  { color: var(--text-primary); cursor: default; }
.crumb:not(.last)::after { content: ' /'; color: var(--text-dimmed); margin-left: 4px; }

.progress-bar-wrap {
  position: relative; height: 24px; background: var(--bg-surface);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  overflow: hidden; margin-bottom: 16px;
}
.progress-bar-inner { height: 100%; background: var(--accent); transition: width 0.3s; }
.progress-text {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  font-size: 11px; color: var(--text-primary); white-space: nowrap;
}

.viz-list { display: flex; flex-direction: column; gap: 3px; }
.viz-header {
  display: grid; grid-template-columns: 1fr 100px 200px;
  font-size: 11px; color: var(--text-dimmed); padding: 4px 12px;
  text-transform: uppercase; letter-spacing: .5px;
}
.viz-row {
  display: grid; grid-template-columns: 20px 1fr 100px 200px;
  align-items: center; gap: 8px;
  padding: 8px 12px; background: var(--bg-card);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  transition: background 0.1s;
}
.viz-row.dir { cursor: pointer; }
.viz-row.dir:hover { background: var(--bg-hover); border-color: var(--accent); }
.viz-icon { font-size: 12px; color: var(--text-dimmed); }
.viz-icon.icon-dir::before  { content: '[D]'; color: var(--accent); font-size: 10px; font-weight: 700; letter-spacing: -.5px; }
.viz-icon.icon-file::before { content: '[F]'; font-size: 10px; font-weight: 700; letter-spacing: -.5px; }
.viz-name { font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.viz-size { font-size: 12px; color: var(--text-secondary); text-align: right; font-variant-numeric: tabular-nums; }
.viz-bar-wrap { display: flex; align-items: center; gap: 8px; }
.viz-bar { height: 8px; border-radius: 4px; transition: width 0.3s; min-width: 2px; }
.viz-pct { font-size: 11px; color: var(--text-dimmed); width: 40px; flex-shrink: 0; font-variant-numeric: tabular-nums; }

.empty-hint { text-align: center; padding: 40px; color: var(--text-dimmed); font-size: 14px; }
</style>
