import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/context-menu',
    name: 'ContextMenu',
    component: () => import('@/views/ContextMenuView.vue'),
  },
  {
    path: '/disk',
    name: 'Disk',
    component: () => import('@/views/DiskView.vue'),
  },
  {
    path: '/downloads',
    name: 'Downloads',
    component: () => import('@/views/DownloadsView.vue'),
  },
  {
    path: '/gallery',
    name: 'Gallery',
    component: () => import('@/views/GalleryView.vue'),
  },
  {
    path: '/cleanup',
    name: 'Cleanup',
    component: () => import('@/views/CleanupView.vue'),
  },
  {
    path: '/preferences',
    name: 'Preferences',
    component: () => import('@/views/PreferencesView.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 离开下载页时隐藏 WebContentsView，避免原生层覆盖其他页面
router.beforeEach((to, from) => {
  if (from.name === 'Downloads' && to.name !== 'Downloads') {
    if (typeof window !== 'undefined' && window.electronAPI?.browserViewHide) {
      window.electronAPI.browserViewHide()
    }
  }
})

export default router
