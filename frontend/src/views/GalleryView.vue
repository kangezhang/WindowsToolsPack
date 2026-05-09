<template>
  <div class="gallery-view">
    <div class="page-header">
      <div>
        <h2>图片画廊</h2>
        <p class="page-desc">快速浏览目录内的图片</p>
      </div>
    </div>

    <!-- 路径输入 -->
    <div class="path-row">
      <input
        v-model="scanPath"
        class="path-input"
        placeholder="输入图片目录路径…"
        @keyup.enter="startScan"
      />
      <label class="checkbox-label">
        <input type="checkbox" v-model="recursive" />
        递归子目录
      </label>
      <button class="btn btn-primary" @click="startScan" :disabled="scanning">
        {{ scanning ? '扫描中…' : '扫描' }}
      </button>
    </div>

    <div v-if="error" class="error-bar">{{ error }}</div>

    <!-- 工具栏 -->
    <div v-if="images.length" class="toolbar">
      <span class="count-text">共 {{ images.length }} 张图片</span>
      <input v-model="search" class="search-input" placeholder="搜索文件名…" />
      <div class="size-buttons">
        <button :class="['btn btn-xs', thumbSize === 120 && 'btn-primary']" @click="thumbSize = 120">小</button>
        <button :class="['btn btn-xs', thumbSize === 180 && 'btn-primary']" @click="thumbSize = 180">中</button>
        <button :class="['btn btn-xs', thumbSize === 260 && 'btn-primary']" @click="thumbSize = 260">大</button>
      </div>
    </div>

    <!-- 图片网格 -->
    <div
      v-if="filtered.length"
      class="image-grid"
      :style="{ gridTemplateColumns: `repeat(auto-fill, minmax(${thumbSize}px, 1fr))` }"
    >
      <div
        v-for="img in filtered"
        :key="img.path"
        class="img-cell"
        @click="openLightbox(img)"
        :title="img.name"
      >
        <img
          :src="thumbUrl(img.path)"
          :alt="img.name"
          class="img-thumb"
          :style="{ height: thumbSize * 0.75 + 'px' }"
          loading="lazy"
          @error="$event.target.src = '/placeholder.svg'"
        />
        <div class="img-name">{{ img.name }}</div>
      </div>
    </div>

    <div v-else-if="!scanning && scanned" class="empty-hint">未找到图片</div>

    <!-- Lightbox -->
    <div v-if="lightbox" class="lightbox" @click.self="lightbox = null" @keyup.esc="lightbox = null" tabindex="0">
      <button class="lb-close" @click="lightbox = null">✕</button>
      <button class="lb-nav lb-prev" @click="prevImage" :disabled="lightboxIdx === 0">‹</button>
      <div class="lb-img-wrap">
        <img :src="thumbUrl(lightbox.path, 1200)" class="lb-img" />
        <div class="lb-caption">
          <span class="lb-name">{{ lightbox.name }}</span>
          <span class="lb-size">{{ formatBytes(lightbox.size) }}</span>
          <button class="btn btn-xs btn-primary" @click="openFile(lightbox.path)">用外部程序打开</button>
        </div>
      </div>
      <button class="lb-nav lb-next" @click="nextImage" :disabled="lightboxIdx === filtered.length - 1">›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { galleryApi } from '@/api/gallery.js'

const scanPath  = ref('')
const recursive = ref(true)
const scanning  = ref(false)
const scanned   = ref(false)
const error     = ref('')
const images    = ref([])
const search    = ref('')
const thumbSize = ref(180)
const lightbox    = ref(null)
const lightboxIdx = ref(0)

const filtered = computed(() => {
  if (!search.value) return images.value
  const q = search.value.toLowerCase()
  return images.value.filter(i => i.name.toLowerCase().includes(q))
})

function thumbUrl(path, size = 200) {
  return galleryApi.thumbnailUrl(path, size)
}

async function startScan() {
  if (!scanPath.value.trim()) return
  scanning.value = true
  scanned.value  = false
  error.value    = ''
  images.value   = []

  try {
    const { task_id } = await galleryApi.startScan(scanPath.value.trim(), recursive.value)
    const ws = galleryApi.scanWs(task_id)

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'done') {
        images.value   = msg.images || []
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

function openLightbox(img) {
  lightboxIdx.value = filtered.value.indexOf(img)
  lightbox.value    = img
}

function prevImage() {
  if (lightboxIdx.value > 0) {
    lightboxIdx.value--
    lightbox.value = filtered.value[lightboxIdx.value]
  }
}

function nextImage() {
  if (lightboxIdx.value < filtered.value.length - 1) {
    lightboxIdx.value++
    lightbox.value = filtered.value[lightboxIdx.value]
  }
}

async function openFile(path) {
  try { await galleryApi.openFile(path) } catch {}
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let v = bytes, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(1)} ${units[i]}`
}
</script>

<style scoped>
.gallery-view { width: 100%; max-width: 1100px; margin: 0 auto; padding: 24px; overflow-y: auto; box-sizing: border-box; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; color: var(--text-primary); }
.page-desc { font-size: 12px; color: var(--text-secondary); margin: 0; }

.path-row { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.path-input {
  flex: 1; padding: 9px 14px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px;
}
.path-input:focus { outline: none; border-color: var(--accent); }
.checkbox-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); white-space: nowrap; cursor: pointer; }

.error-bar {
  padding: 10px 16px; margin-bottom: 16px;
  background: rgba(250,82,82,.1); border: 1px solid rgba(250,82,82,.3);
  border-radius: var(--radius-sm); font-size: 13px; color: var(--danger);
}

.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.count-text { font-size: 13px; color: var(--text-dimmed); white-space: nowrap; }
.search-input {
  flex: 1; padding: 7px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px;
}
.search-input:focus { outline: none; border-color: var(--accent); }
.size-buttons { display: flex; gap: 4px; }

.image-grid { display: grid; gap: 12px; }
.img-cell { cursor: pointer; border-radius: var(--radius-sm); overflow: hidden; background: var(--bg-card); border: 1px solid var(--border); transition: border-color 0.1s, transform 0.1s; }
.img-cell:hover { border-color: var(--accent); transform: translateY(-2px); }
.img-thumb { width: 100%; object-fit: cover; display: block; }
.img-name { font-size: 11px; color: var(--text-dimmed); padding: 5px 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.empty-hint { text-align: center; padding: 40px; color: var(--text-dimmed); font-size: 14px; }

/* Lightbox */
.lightbox {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,.92);
  display: flex; align-items: center; justify-content: center;
}
.lb-close {
  position: absolute; top: 16px; right: 20px;
  background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; padding: 4px 8px;
}
.lb-close:hover { color: var(--danger); }
.lb-nav {
  position: absolute; top: 50%; transform: translateY(-50%);
  background: rgba(255,255,255,.1); border: none; color: #fff;
  font-size: 48px; line-height: 1; padding: 8px 16px; cursor: pointer;
  border-radius: var(--radius-sm); transition: background 0.15s;
}
.lb-nav:hover:not(:disabled) { background: rgba(255,255,255,.25); }
.lb-nav:disabled { opacity: 0.2; cursor: default; }
.lb-prev { left: 20px; }
.lb-next { right: 20px; }
.lb-img-wrap { max-width: 90vw; max-height: 90vh; display: flex; flex-direction: column; align-items: center; gap: 12px; }
.lb-img { max-width: 100%; max-height: 80vh; object-fit: contain; border-radius: var(--radius-sm); }
.lb-caption { display: flex; align-items: center; gap: 12px; font-size: 13px; color: rgba(255,255,255,.7); }
.lb-name { font-weight: 500; }
.lb-size { opacity: 0.6; }
</style>
