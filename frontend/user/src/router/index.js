import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('../views/Layout.vue'),
    redirect: '/chat',
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('../views/Chat.vue'),
      },
      {
        path: 'resume',
        name: 'Resume',
        component: () => import('../views/Resume.vue'),
      },
      {
        path: 'interview',
        name: 'Interview',
        component: () => import('../views/Interview.vue'),
      },
      {
        path: 'code',
        name: 'CodeCheck',
        component: () => import('../views/CodeCheck.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router
