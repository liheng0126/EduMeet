import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/', component: () => import('../views/ChatView.vue') },
    { path: '/articles', component: () => import('../views/ArticlesView.vue') },
  ],
})

// 路由守卫：未登录跳转登录页
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.token) return '/login'
})

export default router
