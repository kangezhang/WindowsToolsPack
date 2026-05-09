<template>
  <div class="cleanup-view">
    <div class="page-header">
      <div>
        <h2>磁盘清理</h2>
        <p class="page-desc">扫描并清理临时文件、浏览器缓存等垃圾文件</p>
      </div>
    </div>

    <!-- 规则选择 -->
    <div class="rules-panel card" v-if="rules.length">
      <div class="rules-title">选择清理规则</div>
      <div class="rules-grid">
        <label
          v-for="rule in rules"
          :key="rule.name"
          class="rule-item"
          :class="{ selected: selectedRules.has(rule.name), danger: rule.risk_level === 'high' }"
        >
          <input type="checkbox" :checked="selectedRules.has(rule.name)" @change="toggleRule(rule.name)" />
          <div class="rule-info">
            <div class="rule-name">{{ rule.name }}</div>
            <div class="rule-desc">{{ rule.description }}</div>
            <span v-if="rule.risk_level === 'high'" class="risk-badge">高风险</span>
          </div>
        </label>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-row">
      <button
        class="btn btn-primary"
        @click="startScan"
        :disabled="scanning || !selectedRules.size"
      >
        {{ scanning ? '扫描中…' : '开始扫描' }}
      </button>
      <button
        v-if="scanItems.length"
        class="btn btn-danger"
        @click="executeCleanup"
        :disabled="executing || !checkedPaths.size"
      >
        {{ executing ? '清理中…' : `清理选中 (${checkedPaths.size} 项)` }}
      </button>
      <button v-if="scanItems.length" class="btn" @click="toggleSelectAll">
        {{ checkedPaths.size === scanItems.length ? '取消全选' : '全选' }}
      </button>
    </div>

    <div v-if="error" class="error-bar">{{ error }}</div>

    <!-- 扫描进度 -->
    <div v-if="scanning" class="progress-hint">正在扫描，请稍候…</div>

    <!-- 清理进度 -->
    <div v-if="executing" class="exec-progress card">
      <div class="exec-bar-wrap">
        <div class="exec-bar" :style="{ width: execProgress + '%' }"></div>
      </div>
      <div class="exec-text">已删除 {{ execDeleted }} / {{ execTotal }}，失败 {{ execFailed }}</div>
    </div>

    <!-- 完成摘要 -->
    <div v-if="summary" class="summary-card card">
      <span>清理完成：删除 <strong>{{ summary.deleted }}</strong> 项，失败 <strong>{{ summary.failed }}</strong> 项，释放 <strong>{{ formatBytes(summary.freed_bytes) }}</strong></span>
    </div>

    <!-- 扫描结果列表 -->
    <div v-if="scanItems.length" class="result-summary">
      找到 {{ scanItems.length }} 项垃圾文件，共 {{ formatBytes(totalSize) }}
    </div>

    <div class="scan-list" v-if="scanItems.length">
      <div
        v-for="item in groupedItems"
        :key="item.rule_name"
        class="rule-group"
      >
        <div class="group-header" @click="toggleGroup(item.rule_name)">
          <input type="checkbox"
            :checked="isGroupChecked(item.rule_name)"
            :indeterminate="isGroupIndeterminate(item.rule_name)"
            @change="toggleGroupCheck(item.rule_name)"
            @click.stop
          />
          <span class="group-icon">{{ expanded.has(item.rule_name) ? '▼' : '▶' }}</span>
          <span class="group-name">{{ item.rule_name }}</span>
          <span class="group-meta">{{ item.paths.length }} 项 · {{ formatBytes(item.total) }}</span>
        </div>

        <div v-if="expanded.has(item.rule_name)" class="group-items">
          <div
            v-for="path in item.paths"
            :key="path"
            class="scan-row"
            :class="{ checked: checkedPaths.has(path) }"
          >
            <input type="checkbox" :checked="checkedPaths.has(path)" @change="togglePath(path)" />
            <span class="scan-path">{{ path }}</span>
            <span class="scan-size">{{ formatBytes(item.sizes[path] || 0) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!scanning && scanned" class="empty-hint">没有找到垃圾文件</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { cleanupApi } from '@/api/cleanup.js'

const rules        = ref([])
const selectedRules = ref(new Set())
const scanning     = ref(false)
const scanned      = ref(false)
const executing    = ref(false)
const error        = ref('')
const scanItems    = ref([])  // [{path, size, rule_name, category, risk_level}]
const checkedPaths = ref(new Set())
const expanded     = ref(new Set())
const summary      = ref(null)

const execProgress = ref(0)
const execDeleted  = ref(0)
const execFailed   = ref(0)
const execTotal    = ref(0)

const totalSize = computed(() => scanItems.value.reduce((s, i) => s + (i.size || 0), 0))

const groupedItems = computed(() => {
  const map = {}
  for (const item of scanItems.value) {
    if (!map[item.rule_name]) map[item.rule_name] = { rule_name: item.rule_name, paths: [], sizes: {}, total: 0 }
    map[item.rule_name].paths.push(item.path)
    map[item.rule_name].sizes[item.path] = item.size || 0
    map[item.rule_name].total += item.size || 0
  }
  return Object.values(map)
})

function toggleRule(name) {
  const s = new Set(selectedRules.value)
  if (s.has(name)) s.delete(name); else s.add(name)
  selectedRules.value = s
}

function togglePath(path) {
  const s = new Set(checkedPaths.value)
  if (s.has(path)) s.delete(path); else s.add(path)
  checkedPaths.value = s
}

function toggleSelectAll() {
  if (checkedPaths.value.size === scanItems.value.length) {
    checkedPaths.value = new Set()
  } else {
    checkedPaths.value = new Set(scanItems.value.map(i => i.path))
  }
}

function toggleGroup(name) {
  const s = new Set(expanded.value)
  if (s.has(name)) s.delete(name); else s.add(name)
  expanded.value = s
}

function isGroupChecked(name) {
  const group = groupedItems.value.find(g => g.rule_name === name)
  if (!group) return false
  return group.paths.every(p => checkedPaths.value.has(p))
}

function isGroupIndeterminate(name) {
  const group = groupedItems.value.find(g => g.rule_name === name)
  if (!group) return false
  const count = group.paths.filter(p => checkedPaths.value.has(p)).length
  return count > 0 && count < group.paths.length
}

function toggleGroupCheck(name) {
  const group = groupedItems.value.find(g => g.rule_name === name)
  if (!group) return
  const s = new Set(checkedPaths.value)
  const allChecked = group.paths.every(p => s.has(p))
  if (allChecked) group.paths.forEach(p => s.delete(p))
  else            group.paths.forEach(p => s.add(p))
  checkedPaths.value = s
}

async function startScan() {
  scanning.value = true
  scanned.value  = false
  scanItems.value = []
  checkedPaths.value = new Set()
  summary.value = null
  error.value = ''

  try {
    const { task_id } = await cleanupApi.startScan([...selectedRules.value])
    const ws = cleanupApi.scanWs(task_id)

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'done') {
        scanItems.value = msg.items || []
        checkedPaths.value = new Set(scanItems.value.map(i => i.path))
        // 默认展开所有分组
        expanded.value = new Set(scanItems.value.map(i => i.rule_name))
        scanning.value = false
        scanned.value  = true
        ws.close()
      } else if (msg.type === 'error') {
        error.value    = msg.message
        scanning.value = false
        ws.close()
      }
    }
    ws.onerror = () => { error.value = 'WebSocket 连接失败'; scanning.value = false }
  } catch (e) {
    error.value    = e.message
    scanning.value = false
  }
}

async function executeCleanup() {
  if (!checkedPaths.value.size) return
  const paths = [...checkedPaths.value]
  executing.value  = true
  execProgress.value = 0
  execDeleted.value  = 0
  execFailed.value   = 0
  execTotal.value    = paths.length
  summary.value      = null
  error.value        = ''

  try {
    const { task_id } = await cleanupApi.startExecute(paths)
    const ws = cleanupApi.executeWs(task_id)

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'progress') {
        execDeleted.value  = msg.deleted
        execFailed.value   = msg.failed
        execProgress.value = ((msg.deleted + msg.failed) / execTotal.value) * 100
      } else if (msg.type === 'done') {
        summary.value     = msg.summary
        executing.value   = false
        // 从列表中移除已删除的路径
        const deleted = new Set(paths.filter(p => !false))  // 简化：移除全部选中项
        scanItems.value   = scanItems.value.filter(i => !checkedPaths.value.has(i.path))
        checkedPaths.value = new Set()
        ws.close()
      } else if (msg.type === 'error') {
        error.value    = msg.message
        executing.value = false
        ws.close()
      }
    }
    ws.onerror = () => { error.value = 'WebSocket 连接失败'; executing.value = false }
  } catch (e) {
    error.value     = e.message
    executing.value = false
  }
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let v = bytes, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(1)} ${units[i]}`
}

async function loadRules() {
  try {
    rules.value = await cleanupApi.listRules()
    selectedRules.value = new Set(rules.value.filter(r => r.risk_level !== 'high').map(r => r.name))
  } catch {}
}

onMounted(loadRules)
</script>

<style scoped>
.cleanup-view { width: 100%; max-width: 860px; margin: 0 auto; padding: 24px; overflow-y: auto; box-sizing: border-box; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; color: var(--text-primary); }
.page-desc { font-size: 12px; color: var(--text-secondary); margin: 0; }

.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px; margin-bottom: 16px; }

.rules-panel { margin-bottom: 16px; }
.rules-title { font-weight: 600; font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; }
.rules-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.rule-item {
  display: flex; gap: 10px; padding: 10px 12px; cursor: pointer;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-surface); transition: border-color 0.1s;
}
.rule-item:hover { border-color: var(--accent); }
.rule-item.selected { border-color: var(--accent); background: rgba(34,139,230,.06); }
.rule-item.danger.selected { border-color: var(--danger); background: rgba(250,82,82,.05); }
.rule-info { flex: 1; min-width: 0; }
.rule-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.rule-desc { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
.risk-badge { font-size: 10px; padding: 1px 6px; background: rgba(250,82,82,.15); color: var(--danger); border-radius: 8px; margin-top: 4px; display: inline-block; }

.action-row { display: flex; gap: 10px; margin-bottom: 16px; }

.error-bar { padding: 10px 16px; margin-bottom: 16px; background: rgba(250,82,82,.1); border: 1px solid rgba(250,82,82,.3); border-radius: var(--radius-sm); font-size: 13px; color: var(--danger); }
.progress-hint { text-align: center; padding: 20px; color: var(--text-secondary); font-size: 14px; }

.exec-progress { }
.exec-bar-wrap { height: 8px; background: var(--bg-hover); border-radius: 4px; margin-bottom: 8px; overflow: hidden; }
.exec-bar { height: 100%; background: var(--danger); transition: width 0.4s; }
.exec-text { font-size: 13px; color: var(--text-secondary); }

.summary-card { display: flex; align-items: center; gap: 12px; font-size: 14px; color: var(--text-primary); }
.summary-icon { font-size: 20px; }

.result-summary { font-size: 13px; color: var(--text-secondary); margin-bottom: 10px; }

.scan-list { display: flex; flex-direction: column; gap: 6px; }
.rule-group { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
.group-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; background: var(--bg-surface); cursor: pointer;
  font-size: 13px;
}
.group-header:hover { background: var(--bg-hover); }
.group-icon { font-size: 10px; }
.group-name { flex: 1; font-weight: 600; color: var(--text-primary); }
.group-meta { font-size: 11px; color: var(--text-dimmed); }
.group-items { padding: 4px 0; background: var(--bg-card); }
.scan-row {
  display: flex; align-items: center; gap: 8px; padding: 6px 16px;
  font-size: 12px; transition: background 0.1s;
}
.scan-row:hover { background: var(--bg-hover); }
.scan-row.checked { background: rgba(250,82,82,.04); }
.scan-path { flex: 1; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: monospace; font-size: 11px; }
.scan-size { color: var(--text-dimmed); font-size: 11px; flex-shrink: 0; font-variant-numeric: tabular-nums; }

.empty-hint { text-align: center; padding: 40px; color: var(--text-dimmed); font-size: 14px; }
</style>
