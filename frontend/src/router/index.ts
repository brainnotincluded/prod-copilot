import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: '/chat',
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
    },
    {
      path: '/swagger',
      name: 'swagger',
      component: () => import('@/views/SwaggerView.vue'),
    },
    {
      path: '/endpoints',
      name: 'api-maps',
      component: () => import('@/views/ApiMapsView.vue'),
    },
    // Dashboard temporarily hidden
    // {
    //   path: '/dashboard',
    //   name: 'dashboard',
    //   component: () => import('@/views/DashboardView.vue'),
    // },
  ],
})

export default router
