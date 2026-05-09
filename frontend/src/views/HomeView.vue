<template>
  <div class="home-view">
    <header class="home-header">
      <h1>Windows 工具箱</h1>
      <p class="subtitle">系统效率工具集合</p>
    </header>

    <div class="tool-grid">
      <router-link
        v-for="tool in tools"
        :key="tool.path"
        :to="tool.path"
        class="tool-card"
      >
        <div class="tool-info">
          <div class="tool-name">{{ tool.name }}</div>
          <div class="tool-desc">{{ tool.desc }}</div>
        </div>
        <span class="tool-arrow">›</span>
      </router-link>
    </div>

    <div v-if="sysInfo" class="sys-banner">
      <span>{{ sysInfo.os }} {{ sysInfo.os_version }}</span>
      <span class="sep">|</span>
      <span :class="sysInfo.is_admin ? 'badge-ok' : 'badge-warn'">
        {{ sysInfo.is_admin ? '管理员' : '普通用户' }}
      </span>
      <span class="sep">|</span>
      <span>Python {{ sysInfo.python_version }}</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useSystemStore } from '@/stores/system.js'

const systemStore = useSystemStore()
const { info: sysInfo } = storeToRefs(systemStore)

const tools = [
  { path: '/context-menu', name: '右键菜单管理', desc: '查看、启用、禁用、删除系统右键菜单项' },
  { path: '/disk',         name: '磁盘可视化',   desc: '扫描目录，按大小可视化文件占用' },
  { path: '/downloads',    name: '视频下载',     desc: '支持 Bilibili、YouTube 等主流平台' },
  { path: '/gallery',      name: '图片画廊',     desc: '快速浏览目录内图片，含全屏预览' },
  { path: '/cleanup',      name: '磁盘清理',     desc: '扫描并清理临时文件、浏览器缓存' },
  { path: '/preferences',  name: '偏好设置',     desc: '开机自启、下载路径、ffmpeg 管理' },
]

onMounted(() => {
  if (!sysInfo.value) systemStore.fetchInfo()
})
</script>

<style scoped>
.home-view {
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 24px;
  overflow-y: auto;
  box-sizing: border-box;
}

.home-header {
  margin-bottom: 28px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.home-header h1 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
  letter-spacing: .3px;
}
.subtitle {
  color: var(--text-dimmed);
  font-size: 12px;
  margin: 0;
}

.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: 24px;
}

.tool-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  background: var(--bg-card);
  text-decoration: none;
  color: inherit;
  transition: background 0.1s;
}
.tool-card:hover {
  background: var(--bg-hover);
}
.tool-card:hover .tool-name { color: var(--accent); }

.tool-info { flex: 1; min-width: 0; }
.tool-name { font-weight: 600; font-size: 13px; color: var(--text-primary); margin-bottom: 3px; transition: color 0.1s; }
.tool-desc { font-size: 11px; color: var(--text-dimmed); line-height: 1.4; }
.tool-arrow { font-size: 18px; color: var(--text-dimmed); flex-shrink: 0; }

.sys-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-dimmed);
}
.sep { opacity: 0.3; }
.badge-ok   { color: var(--success); font-weight: 600; }
.badge-warn { color: var(--warning); font-weight: 600; }
</style>
