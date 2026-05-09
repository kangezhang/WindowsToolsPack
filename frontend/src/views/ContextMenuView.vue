<template>
  <div class="cm-view">
    <div class="page-header">
      <div>
        <h2>右键菜单管理</h2>
        <p class="page-desc">管理 Windows 系统右键菜单项，需要管理员权限</p>
      </div>
      <button class="btn btn-primary" @click="loadItems" :disabled="loading">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </div>

    <div v-if="!isAdmin" class="warn-banner">
      当前以普通用户运行，修改操作可能失败。
      <button class="btn btn-sm" @click="elevate">以管理员重启</button>
    </div>

    <div v-if="error" class="error-bar">{{ error }}</div>

    <!-- 搜索 + 筛选 -->
    <div class="toolbar" v-if="items.length">
      <input v-model="search" class="search-input" placeholder="搜索菜单项…" />
      <select v-model="filterCategory" class="select-input">
        <option value="">全部分类</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>

    <!-- 批量操作 -->
    <div class="batch-bar" v-if="selected.size > 0">
      <span>已选 {{ selected.size }} 项</span>
      <button class="btn btn-sm btn-primary" @click="batchEnable">启用</button>
      <button class="btn btn-sm" @click="batchDisable">禁用</button>
      <button class="btn btn-sm btn-danger" @click="batchRemove">删除</button>
      <button class="btn btn-sm" @click="selected.clear()">取消选择</button>
    </div>

    <!-- 列表 -->
    <div v-if="loading && !items.length" class="loading-hint">加载中…</div>

    <div class="cm-list" v-else>
      <div
        v-for="item in filtered"
        :key="item.registry_path"
        class="cm-row"
        :class="{ disabled: item.is_disabled, selected: selected.has(item.registry_path) }"
      >
        <input
          type="checkbox"
          :checked="selected.has(item.registry_path)"
          @change="toggleSelect(item.registry_path)"
        />
        <div class="cm-icon" v-if="item.icon">
          <img :src="iconUrl(item.icon)" @error="$event.target.style.display='none'" width="16" height="16" />
        </div>
        <div class="cm-icon placeholder" v-else></div>
        <div class="cm-body">
          <div class="cm-name">{{ item.name }}</div>
          <div class="cm-cmd">{{ item.command }}</div>
        </div>
        <div class="cm-meta">
          <span class="tag">{{ item.category || '其他' }}</span>
          <span class="tag" :class="!item.is_disabled ? 'tag-ok' : 'tag-off'">{{ !item.is_disabled ? '启用' : '禁用' }}</span>
        </div>
        <div class="cm-actions">
          <button v-if="item.is_disabled" class="btn btn-xs btn-primary" @click="enable(item)">启用</button>
          <button v-else class="btn btn-xs" @click="disable(item)">禁用</button>
          <button class="btn btn-xs btn-danger" @click="remove(item)">删除</button>
        </div>
      </div>
      <div v-if="!filtered.length && !loading" class="empty-hint">
        {{ items.length ? '没有匹配的菜单项' : '未找到任何右键菜单项' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useSystemStore } from '@/stores/system.js'
import { contextMenuApi } from '@/api/contextMenu.js'

const systemStore = useSystemStore()
const { info: sysInfo } = storeToRefs(systemStore)
const isAdmin = computed(() => sysInfo.value?.is_admin ?? true)

const items    = ref([])
const loading  = ref(false)
const error    = ref('')
const search   = ref('')
const filterCategory = ref('')
const selected = ref(new Set())

const categories = computed(() => [...new Set(items.value.map(i => i.category).filter(Boolean))])

const filtered = computed(() => {
  let list = items.value
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q) || (i.command || '').toLowerCase().includes(q))
  }
  if (filterCategory.value) {
    list = list.filter(i => i.category === filterCategory.value)
  }
  return list
})

function iconUrl(iconPath) {
  if (!iconPath) return ''
  return `/api/system/icon?path=${encodeURIComponent(iconPath)}`
}

function toggleSelect(path) {
  const s = new Set(selected.value)
  if (s.has(path)) s.delete(path); else s.add(path)
  selected.value = s
}

async function loadItems() {
  loading.value = true
  error.value = ''
  try {
    items.value = await contextMenuApi.list()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function enable(item) {
  try {
    await contextMenuApi.enable([item.registry_path])
    item.is_disabled = false
  } catch (e) { error.value = e.message }
}

async function disable(item) {
  try {
    await contextMenuApi.disable([item.registry_path])
    item.is_disabled = true
  } catch (e) { error.value = e.message }
}

async function remove(item) {
  if (!confirm(`确定删除「${item.name}」？此操作不可撤销。`)) return
  try {
    await contextMenuApi.remove([item.registry_path])
    items.value = items.value.filter(i => i.registry_path !== item.registry_path)
  } catch (e) { error.value = e.message }
}

async function batchEnable() {
  const paths = [...selected.value]
  try {
    await contextMenuApi.enable(paths)
    items.value.forEach(i => { if (selected.value.has(i.registry_path)) i.is_disabled = false })
    selected.value = new Set()
  } catch (e) { error.value = e.message }
}

async function batchDisable() {
  const paths = [...selected.value]
  try {
    await contextMenuApi.disable(paths)
    items.value.forEach(i => { if (selected.value.has(i.registry_path)) i.is_disabled = true })
    selected.value = new Set()
  } catch (e) { error.value = e.message }
}

async function batchRemove() {
  if (!confirm(`确定删除选中的 ${selected.value.size} 项？`)) return
  const paths = [...selected.value]
  try {
    await contextMenuApi.remove(paths)
    items.value = items.value.filter(i => !selected.value.has(i.registry_path))
    selected.value = new Set()
  } catch (e) { error.value = e.message }
}

async function elevate() {
  try { await systemStore.elevate() } catch {}
}

onMounted(async () => {
  if (!sysInfo.value) await systemStore.fetchInfo()
  await loadItems()
})
</script>

<style scoped>
.cm-view { width: 100%; max-width: 900px; margin: 0 auto; padding: 24px; overflow-y: auto; box-sizing: border-box; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; color: var(--text-primary); }
.page-desc { font-size: 12px; color: var(--text-secondary); margin: 0; }

.warn-banner {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; margin-bottom: 16px;
  background: rgba(255,193,7,.1); border: 1px solid rgba(255,193,7,.3);
  border-radius: var(--radius-sm); font-size: 13px; color: var(--warning);
}

.error-bar {
  padding: 10px 16px; margin-bottom: 16px;
  background: rgba(250,82,82,.1); border: 1px solid rgba(250,82,82,.3);
  border-radius: var(--radius-sm); font-size: 13px; color: var(--danger);
}

.toolbar { display: flex; gap: 10px; margin-bottom: 12px; }
.search-input {
  flex: 1; padding: 7px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px;
}
.search-input:focus { outline: none; border-color: var(--accent); }
.select-input {
  padding: 7px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px; cursor: pointer;
}

.batch-bar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
  padding: 8px 12px; background: var(--accent-dim);
  border: 1px solid rgba(232,115,10,.25); border-radius: var(--radius-sm);
  font-size: 13px; color: var(--text-secondary);
}

.cm-list { display: flex; flex-direction: column; gap: 2px; }

.cm-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-card);
  transition: background 0.1s;
}
.cm-row:hover { background: var(--bg-hover); }
.cm-row.disabled { opacity: 0.55; }
.cm-row.selected { border-color: var(--accent); background: var(--accent-dim); }

.cm-icon { width: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 14px; }

.cm-body { flex: 1; min-width: 0; }
.cm-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.cm-cmd  { font-size: 11px; color: var(--text-dimmed); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }

.cm-meta { display: flex; gap: 6px; flex-shrink: 0; }
.tag     { font-size: 11px; padding: 2px 7px; border-radius: 10px; background: rgba(255,255,255,.06); color: var(--text-secondary); }
.tag-ok  { background: rgba(55,178,77,.15); color: var(--success); }
.tag-off { background: rgba(134,142,150,.15); color: var(--text-dimmed); }

.cm-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-xs { padding: 3px 8px; font-size: 11px; }

.loading-hint, .empty-hint {
  text-align: center; padding: 40px;
  color: var(--text-dimmed); font-size: 14px;
}
</style>
