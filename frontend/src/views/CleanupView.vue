<template>
  <div class="cleanup-view">
    <div class="page-header">
      <div>
        <h2>磁盘清理</h2>
        <p class="page-desc">先选清理范围，扫描确认后再删除。</p>
      </div>
      <button class="btn" @click="loadDiagnosis" :disabled="diagnosing || busy">
        {{ diagnosing ? '刷新中...' : '刷新容量' }}
      </button>
    </div>

    <div v-if="diagnosisError" class="error-bar">{{ diagnosisError }}</div>
    <div v-if="error" class="error-bar">{{ error }}</div>

    <section class="workbench">
      <div class="tool-panel">
        <div class="primary-actions">
          <button class="action-button safe" @click="runAction('safe_cleanup')" :disabled="busy">
            <span>一键安全清理</span>
            <strong>{{ actionRunning === 'safe_cleanup' ? '正在清理...' : safeReclaimLabel }}</strong>
          </button>
          <button class="action-button aggressive" @click="confirmAndRun('aggressive_cleanup')" :disabled="busy">
            <span>一键激进清理</span>
            <strong>{{ actionRunning === 'aggressive_cleanup' ? '正在清理...' : aggressiveReclaimLabel }}</strong>
          </button>
          <button class="action-button scan" @click="startScan" :disabled="scanning || executing || actionRunning || !selectedRules.size">
            <span>扫描选中项</span>
            <strong>{{ scanning ? '正在扫描...' : `已选 ${selectedRules.size} 类` }}</strong>
          </button>
          <button class="action-button delete" @click="executeCleanup" :disabled="executing || scanning || actionRunning || !checkedPaths.size">
            <span>清理扫描结果</span>
            <strong>{{ executing ? '正在清理...' : cleanupButtonLabel }}</strong>
          </button>
        </div>

        <div class="selection-bar">
          <div>
            <strong>清理范围</strong>
            <span>{{ rules.length ? `推荐已选 ${selectedRules.size} / ${rules.length} 类` : '正在加载清理规则' }}</span>
          </div>
          <div class="selection-actions">
            <button class="btn btn-sm" @click="selectDefaultRules" :disabled="busy || !rules.length">推荐项</button>
            <button class="btn btn-sm" @click="selectSafeAndLowRules" :disabled="busy || !rules.length">安全+低风险</button>
            <button class="btn btn-sm" @click="selectAggressiveRules" :disabled="busy || !rules.length">激进-含模型</button>
            <button class="btn btn-sm" @click="clearRuleSelection" :disabled="busy || !selectedRules.size">清空</button>
          </div>
        </div>

        <div class="rules-grid" v-if="rules.length">
          <label
            v-for="rule in rules"
            :key="rule.name"
            class="rule-pill"
            :class="{ selected: selectedRules.has(rule.name), danger: rule.risk_level === 'high' }"
            :title="rule.description"
          >
            <input type="checkbox" :checked="selectedRules.has(rule.name)" @change="toggleRule(rule.name)" />
            <span class="rule-name">{{ rule.name }}</span>
            <span class="risk-badge" :class="`risk-${rule.risk_level}`">{{ riskText(rule.risk_level) }}</span>
          </label>
        </div>
      </div>

      <aside class="capacity-panel">
        <div class="capacity-row">
          <span>C 盘剩余</span>
          <strong :class="{ critical: usedPercent(diagnosis?.c_drive) > 95 }">{{ diagnosis?.c_drive?.free_gb ?? '-' }} GB</strong>
        </div>
        <div class="capacity-row" v-if="diagnosis?.d_drive">
          <span>D 盘剩余</span>
          <strong :class="{ critical: usedPercent(diagnosis?.d_drive) > 95 }">{{ diagnosis.d_drive.free_gb }} GB</strong>
        </div>
        <div class="meter">
          <div class="meter-fill danger" :style="{ width: usedPercent(diagnosis?.c_drive) + '%' }"></div>
        </div>
        <div class="capacity-row">
          <span>安全可清理</span>
          <strong>{{ diagnosis?.totals?.safe_reclaim_gb ?? '-' }} GB</strong>
        </div>
        <div class="capacity-row" v-if="diagnosis?.totals?.aggressive_reclaim_gb">
          <span>激进可清理</span>
          <strong class="aggressive-num">{{ diagnosis?.totals?.aggressive_reclaim_gb }} GB</strong>
        </div>
        <div class="capacity-row" v-if="diagnosis?.hiberfil?.exists">
          <span>休眠文件</span>
          <strong class="aggressive-num">{{ diagnosis.hiberfil.size_gb }} GB</strong>
        </div>
        <div class="capacity-row" v-if="diagnosis?.pagefile?.potential_reclaim_gb">
          <span>页面文件可减</span>
          <strong class="aggressive-num">{{ diagnosis.pagefile.potential_reclaim_gb }} GB</strong>
        </div>
        <div class="capacity-row">
          <span>当前勾选</span>
          <strong>{{ scanItems.length ? formatBytes(checkedSize) : `${selectedRules.size} 类` }}</strong>
        </div>
      </aside>
    </section>

    <section class="results-panel" v-if="scanning || scanned || scanItems.length || executing || summary">
      <div class="results-header">
        <div>
          <strong>扫描结果</strong>
          <span v-if="scanItems.length">找到 {{ scanItems.length }} 项，可释放约 {{ formatBytes(totalSize) }}</span>
          <span v-else-if="scanning">正在扫描...</span>
          <span v-else>没有找到可清理项</span>
        </div>
        <button v-if="scanItems.length" class="btn btn-sm" @click="toggleSelectAll" :disabled="executing || actionRunning">
          {{ checkedPaths.size === scanItems.length ? '取消全选' : '全选' }}
        </button>
      </div>

      <div v-if="executing" class="exec-progress">
        <div class="exec-bar-wrap">
          <div class="exec-bar" :style="{ width: execProgress + '%' }"></div>
        </div>
        <div class="exec-text">已处理 {{ execDeleted + execFailed }} / {{ execTotal }}，失败 {{ execFailed }}</div>
      </div>

      <div v-if="summary" class="summary-card">
        清理完成：删除 <strong>{{ summary.deleted }}</strong> 项，失败 <strong>{{ summary.failed }}</strong> 项，释放 <strong>{{ formatBytes(summary.freed_bytes) }}</strong>
      </div>

      <div class="scan-list" v-if="scanItems.length">
        <div v-for="group in groupedItems" :key="group.rule_name" class="rule-group">
          <div class="group-header" @click="toggleGroup(group.rule_name)">
            <input
              type="checkbox"
              :checked="isGroupChecked(group.rule_name)"
              :indeterminate="isGroupIndeterminate(group.rule_name)"
              @change="toggleGroupCheck(group.rule_name)"
              @click.stop
            />
            <span class="group-icon">{{ expanded.has(group.rule_name) ? 'v' : '>' }}</span>
            <span class="group-name">{{ group.rule_name }}</span>
            <span class="group-meta">{{ group.items.length }} 项 · {{ formatBytes(group.total) }}</span>
          </div>

          <div v-if="expanded.has(group.rule_name)" class="group-items">
            <div v-for="item in group.items" :key="item.path" class="scan-row" :class="{ checked: checkedPaths.has(item.path) }">
              <input type="checkbox" :checked="checkedPaths.has(item.path)" @change="togglePath(item.path)" />
              <span class="scan-path" :title="item.path">{{ item.path }}</span>
              <span class="scan-size">{{ formatBytes(item.size || 0) }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div v-if="actionRunning && actionRunning !== 'safe_cleanup'" class="progress-hint">
      正在执行：{{ actionTitle(actionRunning) }}...
    </div>

    <div v-if="actionResult" class="action-result">
      <div class="result-header">
        <strong>{{ actionResult.title }}</strong>
        <span class="status-badge" :class="`status-${actionResult.status}`">{{ statusText(actionResult.status) }}</span>
      </div>
      <div class="result-summary-line">
        <span>释放 {{ formatBytes(actionResult.freed_bytes) }}</span>
        <span>删除 {{ actionResult.deleted || 0 }} 项</span>
        <span>失败 {{ actionResult.failed || 0 }} 项</span>
        <span v-if="actionResult.restart_required" class="restart-note">需要重启</span>
      </div>
      <p v-if="actionResult.message" class="result-message">{{ actionResult.message }}</p>
      <div class="step-list">
        <div v-for="(step, index) in actionResult.steps || []" :key="index" class="step-row">
          <span class="step-status" :class="`step-${step.status}`">{{ statusText(step.status) }}</span>
          <span class="step-label">{{ step.label || step.path }}</span>
          <span class="step-message" :title="step.message">{{ step.message }}</span>
        </div>
      </div>
    </div>

    <section class="maintenance-grid">
      <button class="maintenance-action high" @click="confirmAndRun('disable_hibernation')" :disabled="busy">
        <span>禁用休眠</span>
        <strong>释放 hiberfil.sys</strong>
      </button>
      <button class="maintenance-action high" @click="confirmAndRun('optimize_pagefile')" :disabled="busy">
        <span>页面文件</span>
        <strong>C 盘保留 4-8GB</strong>
      </button>
      <button class="maintenance-action" @click="confirmAndRun('windows_update_cleanup')" :disabled="busy">
        <span>更新缓存</span>
        <strong>清理 SoftwareDistribution</strong>
      </button>
      <button class="maintenance-action high" @click="confirmAndRun('d_drive_cleanup')" :disabled="busy">
        <span>D盘项目清理</span>
        <strong>target / deploy / WXWork</strong>
      </button>
      <button class="maintenance-action" @click="confirmAndRun('component_cleanup')" :disabled="busy">
        <span>组件清理</span>
        <strong>DISM 清理 WinSxS</strong>
      </button>
      <button class="maintenance-action" @click="confirmAndRun('migrate_caches')" :disabled="busy">
        <span>迁移缓存</span>
        <strong>新缓存指向 D 盘</strong>
      </button>
    </section>

    <details class="diagnosis-details" v-if="diagnosis">
      <summary>体检明细和占用建议</summary>
      <div class="detail-grid">
        <div v-for="item in topDiagnosisItems" :key="item.path" class="diagnosis-row">
          <div class="item-main">
            <span class="item-name">{{ item.label }}</span>
            <span class="item-path" :title="item.path">{{ item.path }}</span>
          </div>
          <span class="risk-badge" :class="`risk-${item.risk}`">{{ riskText(item.risk) }}</span>
          <span class="item-size">{{ formatBytes(item.size) }}</span>
          <span class="item-action">{{ item.action }}</span>
        </div>
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { cleanupApi } from '@/api/cleanup.js'

const diagnosis = ref(null)
const diagnosing = ref(false)
const diagnosisError = ref('')
const actionRunning = ref('')
const actionResult = ref(null)

const rules = ref([])
const selectedRules = ref(new Set())
const scanning = ref(false)
const scanned = ref(false)
const executing = ref(false)
const error = ref('')
const scanItems = ref([])
const checkedPaths = ref(new Set())
const expanded = ref(new Set())
const summary = ref(null)

const execProgress = ref(0)
const execDeleted = ref(0)
const execFailed = ref(0)
const execTotal = ref(0)

const busy = computed(() => diagnosing.value || scanning.value || executing.value || !!actionRunning.value)
const totalSize = computed(() => scanItems.value.reduce((sum, item) => sum + (item.size || 0), 0))
const checkedSize = computed(() => scanItems.value.reduce((sum, item) => checkedPaths.value.has(item.path) ? sum + (item.size || 0) : sum, 0))
const topDiagnosisItems = computed(() => (diagnosis.value?.items || []).slice(0, 12))
const safeReclaimLabel = computed(() => {
  const value = diagnosis.value?.totals?.safe_reclaim_gb
  return value === undefined ? '清理临时文件' : `约 ${value} GB`
})
const aggressiveReclaimLabel = computed(() => {
  const value = diagnosis.value?.totals?.aggressive_reclaim_gb
  return value ? `含模型约 ${value} GB` : '日志+回收站+缓存'
})
const cleanupButtonLabel = computed(() => checkedPaths.value.size ? `${checkedPaths.value.size} 项 / ${formatBytes(checkedSize.value)}` : '先扫描并勾选')

const groupedItems = computed(() => {
  const map = {}
  for (const item of scanItems.value) {
    if (!map[item.rule_name]) {
      map[item.rule_name] = { rule_name: item.rule_name, items: [], total: 0 }
    }
    map[item.rule_name].items.push(item)
    map[item.rule_name].total += item.size || 0
  }
  return Object.values(map)
})

function usedPercent(drive) {
  if (!drive?.total) return 0
  return Math.max(0, Math.min(100, (drive.used / drive.total) * 100))
}

function riskText(risk) {
  const map = {
    safe: '安全',
    low: '低风险',
    medium: '谨慎',
    high: '高风险',
    aggressive: '激进',
    manual: '人工确认',
  }
  return map[risk] || risk || '未知'
}

function statusText(status) {
  const map = {
    done: '完成',
    partial: '部分完成',
    failed: '失败',
    skipped: '跳过',
  }
  return map[status] || status || '未知'
}

function actionTitle(action) {
  const map = {
    safe_cleanup: '安全清理',
    aggressive_cleanup: '激进清理',
    migrate_caches: '迁移开发缓存',
    optimize_pagefile: '优化页面文件',
    component_cleanup: '系统组件清理',
    disable_hibernation: '禁用休眠',
    windows_update_cleanup: 'Windows 更新缓存清理',
    d_drive_cleanup: 'D盘项目清理',
  }
  return map[action] || action
}

function confirmAndRun(action) {
  const messages = {
    aggressive_cleanup: '激进清理会移除临时文件、崩溃转储、Windows 日志、回收站及各类包管理器缓存。继续？',
    migrate_caches: '这会修改用户级缓存路径和 TEMP/TMP 环境变量，新终端生效。继续执行？',
    optimize_pagefile: '这会修改 Windows 页面文件配置，需要管理员权限，并且重启后生效。继续执行？',
    component_cleanup: '这会调用 DISM 清理 Windows 组件存储，执行时间可能较长。继续执行？',
    disable_hibernation: '这会关闭系统休眠并立即删除 hiberfil.sys（可释放约等于物理内存的空间）。继续？',
    windows_update_cleanup: '这会临时停止 Windows Update 与 BITS 服务、清空更新下载缓存后再恢复服务。继续？',
    d_drive_cleanup: '这会清理 D:\\Projects 下的 Rust/Tauri target、D:\\Projects\\visualize_ta\\deploy 的 .stage/release 包，以及 D:\\tmp\\WXWork 缓存。Android SDK 模拟器镜像不会自动删除。继续？',
  }
  if (window.confirm(messages[action] || '确认执行？')) runAction(action)
}

async function runAction(action) {
  actionRunning.value = action
  actionResult.value = null
  error.value = ''
  diagnosisError.value = ''
  try {
    actionResult.value = await cleanupApi.runAction(action)
    await loadDiagnosis()
  } catch (err) {
    actionResult.value = {
      title: actionTitle(action),
      status: 'failed',
      failed: 1,
      freed_bytes: 0,
      deleted: 0,
      restart_required: false,
      message: err.message || '执行失败',
      steps: [],
    }
  } finally {
    actionRunning.value = ''
  }
}

function selectDefaultRules() {
  selectedRules.value = new Set(rules.value.filter(rule => rule.risk_level === 'safe').map(rule => rule.name))
}

function selectSafeAndLowRules() {
  selectedRules.value = new Set(rules.value.filter(rule => ['safe', 'low'].includes(rule.risk_level)).map(rule => rule.name))
}

function selectAggressiveRules() {
  selectedRules.value = new Set(rules.value.filter(rule => ['safe', 'low', 'medium', 'aggressive'].includes(rule.risk_level)).map(rule => rule.name))
}

function clearRuleSelection() {
  selectedRules.value = new Set()
}

function toggleRule(name) {
  const next = new Set(selectedRules.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  selectedRules.value = next
}

function togglePath(path) {
  const next = new Set(checkedPaths.value)
  if (next.has(path)) next.delete(path)
  else next.add(path)
  checkedPaths.value = next
}

function toggleSelectAll() {
  checkedPaths.value = checkedPaths.value.size === scanItems.value.length
    ? new Set()
    : new Set(scanItems.value.map(item => item.path))
}

function toggleGroup(name) {
  const next = new Set(expanded.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  expanded.value = next
}

function isGroupChecked(name) {
  const group = groupedItems.value.find(item => item.rule_name === name)
  return !!group && group.items.every(item => checkedPaths.value.has(item.path))
}

function isGroupIndeterminate(name) {
  const group = groupedItems.value.find(item => item.rule_name === name)
  if (!group) return false
  const count = group.items.filter(item => checkedPaths.value.has(item.path)).length
  return count > 0 && count < group.items.length
}

function toggleGroupCheck(name) {
  const group = groupedItems.value.find(item => item.rule_name === name)
  if (!group) return

  const next = new Set(checkedPaths.value)
  const allChecked = group.items.every(item => next.has(item.path))
  if (allChecked) group.items.forEach(item => next.delete(item.path))
  else group.items.forEach(item => next.add(item.path))
  checkedPaths.value = next
}

async function loadDiagnosis() {
  diagnosing.value = true
  diagnosisError.value = ''
  try {
    diagnosis.value = await cleanupApi.diagnose()
  } catch (err) {
    diagnosisError.value = err.message || 'C 盘体检失败'
  } finally {
    diagnosing.value = false
  }
}

async function startScan() {
  scanning.value = true
  scanned.value = false
  scanItems.value = []
  checkedPaths.value = new Set()
  summary.value = null
  actionResult.value = null
  error.value = ''

  try {
    const { task_id } = await cleanupApi.startScan([...selectedRules.value])
    const ws = cleanupApi.scanWs(task_id)

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'done') {
        scanItems.value = msg.items || []
        checkedPaths.value = new Set(scanItems.value.filter(item => !['high', 'aggressive'].includes(item.risk_level)).map(item => item.path))
        expanded.value = new Set(scanItems.value.map(item => item.rule_name))
        scanning.value = false
        scanned.value = true
        ws.close()
      } else if (msg.type === 'error') {
        error.value = msg.message
        scanning.value = false
        ws.close()
      }
    }
    ws.onerror = () => {
      error.value = 'WebSocket 连接失败'
      scanning.value = false
    }
  } catch (err) {
    error.value = err.message
    scanning.value = false
  }
}

async function executeCleanup() {
  if (!checkedPaths.value.size) return

  const paths = [...checkedPaths.value]
  executing.value = true
  execProgress.value = 0
  execDeleted.value = 0
  execFailed.value = 0
  execTotal.value = paths.length
  summary.value = null
  error.value = ''

  try {
    const { task_id } = await cleanupApi.startExecute(paths)
    const ws = cleanupApi.executeWs(task_id)

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'progress') {
        execDeleted.value = msg.deleted
        execFailed.value = msg.failed
        execProgress.value = ((msg.deleted + msg.failed) / Math.max(1, execTotal.value)) * 100
      } else if (msg.type === 'done') {
        summary.value = msg.summary
        executing.value = false
        scanItems.value = scanItems.value.filter(item => !checkedPaths.value.has(item.path))
        checkedPaths.value = new Set()
        loadDiagnosis()
        ws.close()
      } else if (msg.type === 'error') {
        error.value = msg.message
        executing.value = false
        ws.close()
      }
    }
    ws.onerror = () => {
      error.value = 'WebSocket 连接失败'
      executing.value = false
    }
  } catch (err) {
    error.value = err.message
    executing.value = false
  }
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(1)} ${units[index]}`
}

async function loadRules() {
  try {
    rules.value = await cleanupApi.listRules()
    selectDefaultRules()
  } catch (err) {
    error.value = err.message || '清理规则加载失败'
  }
}

onMounted(() => {
  loadDiagnosis()
  loadRules()
})
</script>

<style scoped>
.cleanup-view {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 24px;
  overflow-y: auto;
  box-sizing: border-box;
}

.page-header,
.workbench,
.primary-actions,
.selection-bar,
.selection-actions,
.results-header,
.result-header,
.result-summary-line,
.step-row {
  display: flex;
  align-items: center;
}

.page-header {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--text-primary);
}

.page-desc,
.selection-bar span,
.capacity-row span,
.group-meta,
.result-message,
.step-message,
.item-path,
.item-action {
  color: var(--text-secondary);
}

.page-desc {
  margin: 0;
  font-size: 12px;
}

.workbench {
  align-items: stretch;
  gap: 14px;
  margin-bottom: 14px;
}

.tool-panel,
.capacity-panel,
.results-panel,
.action-result {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.tool-panel {
  flex: 1;
  min-width: 0;
  padding: 14px;
}

.capacity-panel {
  width: 240px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.primary-actions {
  gap: 10px;
  margin-bottom: 14px;
}

.action-button {
  flex: 1;
  min-width: 0;
  min-height: 82px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  color: var(--text-primary);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.action-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--accent);
  background: var(--bg-hover);
}

.action-button:disabled {
  opacity: .45;
  cursor: not-allowed;
}

.action-button span,
.maintenance-action span {
  display: block;
  margin-bottom: 7px;
  color: var(--text-secondary);
  font-size: 12px;
}

.action-button strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 18px;
}

.action-button.safe {
  border-color: rgba(58, 171, 82, .55);
}

.action-button.aggressive {
  border-color: rgba(214, 51, 132, .55);
}

.action-button.scan {
  border-color: rgba(232, 115, 10, .55);
}

.action-button.delete {
  border-color: rgba(224, 84, 84, .55);
}

.selection-bar {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.selection-bar strong {
  display: block;
  margin-bottom: 2px;
  color: var(--text-primary);
}

.selection-actions {
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 8px;
  max-height: 248px;
  overflow-y: auto;
  padding-right: 4px;
}

.rule-pill {
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
}

.rule-pill:hover {
  border-color: var(--accent);
}

.rule-pill.selected {
  background: rgba(232, 115, 10, .08);
  border-color: var(--accent);
}

.rule-pill.danger.selected {
  background: rgba(224, 84, 84, .08);
  border-color: var(--danger);
}

.rule-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}

.risk-badge {
  display: inline-flex;
  justify-content: center;
  min-width: 54px;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.risk-safe {
  color: var(--success);
  background: rgba(58, 171, 82, .12);
}

.risk-low,
.risk-manual {
  color: var(--warning);
  background: rgba(212, 160, 23, .12);
}

.risk-medium {
  color: #ff922b;
  background: rgba(255, 146, 43, .12);
}

.risk-high {
  color: var(--danger);
  background: rgba(224, 84, 84, .14);
}

.risk-aggressive {
  color: #d63384;
  background: rgba(214, 51, 132, .14);
}

.capacity-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.capacity-row strong {
  color: var(--text-primary);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.capacity-row strong.critical {
  color: var(--danger);
}

.capacity-row strong.aggressive-num {
  color: #d63384;
}

.meter {
  width: 100%;
  height: 7px;
  overflow: hidden;
  border-radius: 4px;
  background: var(--bg-hover);
}

.meter-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--accent);
}

.meter-fill.danger {
  background: var(--danger);
}

.results-panel,
.action-result {
  margin-bottom: 14px;
  padding: 14px;
}

.results-header {
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.results-header strong,
.result-header strong {
  display: block;
  color: var(--text-primary);
}

.results-header span,
.result-summary-line,
.exec-text {
  color: var(--text-secondary);
  font-size: 12px;
}

.scan-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.rule-group {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-surface);
  cursor: pointer;
}

.group-header:hover,
.scan-row:hover {
  background: var(--bg-hover);
}

.group-icon {
  width: 12px;
  font-size: 10px;
}

.group-name {
  flex: 1;
  color: var(--text-primary);
  font-weight: 700;
}

.group-items {
  padding: 4px 0;
  background: var(--bg-card);
}

.scan-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  font-size: 12px;
}

.scan-row.checked {
  background: rgba(224, 84, 84, .04);
}

.scan-path {
  flex: 1;
  min-width: 0;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: Consolas, monospace;
  font-size: 11px;
}

.scan-size,
.item-size {
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.exec-progress {
  margin-top: 12px;
}

.exec-bar-wrap {
  height: 8px;
  background: var(--bg-hover);
  border-radius: 4px;
  margin-bottom: 8px;
  overflow: hidden;
}

.exec-bar {
  height: 100%;
  background: var(--danger);
  transition: width 0.3s;
}

.summary-card {
  margin-top: 12px;
  padding: 10px 12px;
  background: rgba(58, 171, 82, .08);
  border: 1px solid rgba(58, 171, 82, .24);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}

.maintenance-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.maintenance-action {
  min-height: 72px;
  padding: 12px 14px;
  text-align: left;
  color: var(--text-primary);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--warning);
}

.maintenance-action:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--accent);
}

.maintenance-action.high {
  border-left-color: var(--danger);
}

.maintenance-action strong {
  font-size: 14px;
}

.result-header {
  justify-content: space-between;
  margin-bottom: 10px;
}

.result-summary-line {
  gap: 14px;
  flex-wrap: wrap;
}

.restart-note {
  color: var(--warning);
  font-weight: 700;
}

.result-message {
  margin: 8px 0 0;
  font-size: 12px;
}

.step-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.step-row {
  gap: 8px;
  padding: 7px 9px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  min-width: 0;
}

.step-status {
  width: 58px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
}

.step-done {
  color: var(--success);
}

.step-partial,
.step-skipped {
  color: var(--warning);
}

.step-failed {
  color: var(--danger);
}

.step-label {
  min-width: 130px;
  color: var(--text-primary);
  font-size: 12px;
}

.step-message {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
}

.status-done {
  background: rgba(58, 171, 82, .12);
  color: var(--success);
}

.status-partial,
.status-skipped {
  background: rgba(212, 160, 23, .12);
  color: var(--warning);
}

.status-failed {
  background: rgba(224, 84, 84, .12);
  color: var(--danger);
}

.diagnosis-details {
  margin-top: 4px;
  color: var(--text-secondary);
}

.diagnosis-details summary {
  cursor: pointer;
  padding: 8px 0;
  color: var(--text-secondary);
  font-weight: 700;
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.diagnosis-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 68px 86px 104px;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.item-name {
  color: var(--text-primary);
  font-weight: 600;
}

.item-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: Consolas, monospace;
  font-size: 11px;
}

.item-action {
  font-size: 12px;
  text-align: right;
}

.error-bar {
  padding: 10px 16px;
  margin-bottom: 14px;
  background: rgba(224, 84, 84, .1);
  border: 1px solid rgba(224, 84, 84, .3);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--danger);
}

.progress-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
}

@media (max-width: 1000px) {
  .workbench,
  .primary-actions,
  .selection-bar,
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .capacity-panel {
    width: auto;
  }

  .selection-actions {
    justify-content: flex-start;
  }

  .maintenance-grid {
    grid-template-columns: 1fr;
  }

  .diagnosis-row {
    grid-template-columns: minmax(0, 1fr) 68px 78px;
  }

  .item-action {
    display: none;
  }
}
</style>
