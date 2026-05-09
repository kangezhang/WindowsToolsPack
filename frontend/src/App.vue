<template>
  <div class="app-shell">
    <nav class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-text">工具箱</span>
      </div>
      <ul class="nav-list">
        <li v-for="item in navItems" :key="item.path">
          <router-link :to="item.path" class="nav-link" :class="{ active: $route.path === item.path }">
            {{ item.label }}
          </router-link>
        </li>
      </ul>
      <div class="sidebar-footer">
        <div class="status-dot" :class="backendOk ? 'ok' : 'err'"></div>
        <span class="status-text">{{ backendOk ? '后端已连接' : '后端未连接' }}</span>
      </div>
    </nav>

    <main class="main-content">
      <div class="view-wrap">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client.js'

const $route = useRoute()
const backendOk = ref(false)

const navItems = [
  { path: '/',             label: '主页'     },
  { path: '/context-menu', label: '右键菜单' },
  { path: '/disk',         label: '磁盘可视化' },
  { path: '/downloads',    label: '视频下载' },
  { path: '/gallery',      label: '图片画廊' },
  { path: '/cleanup',      label: '磁盘清理' },
  { path: '/preferences',  label: '偏好设置' },
]

onMounted(async () => {
  try {
    await api.get('/health', { skipAuth: true })
    backendOk.value = true
  } catch {
    backendOk.value = false
  }
})
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 180px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 0;
}

.sidebar-brand {
  padding: 18px 16px 14px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 6px;
}
.brand-text {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.nav-list {
  list-style: none;
  padding: 4px 8px;
  flex: 1;
  margin: 0;
}

.nav-link {
  display: block;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 13px;
  transition: background 0.1s, color 0.1s;
  text-decoration: none;
}
.nav-link:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-link.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 16px;
  border-top: 1px solid var(--border);
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.ok  { background: var(--success); }
.status-dot.err { background: var(--danger); }
.status-text { font-size: 11px; color: var(--text-dimmed); }

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* view-wrap 撑满剩余高度，内部组件可 height:100% */
.view-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* keep-alive / component 透传高度 */
.view-wrap :deep(> *) {
  flex: 1;
  min-height: 0;
}
</style>
