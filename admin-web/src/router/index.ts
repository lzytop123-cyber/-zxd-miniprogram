import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/Login.vue') },
    {
      path: '/',
      component: () => import('../layouts/AdminLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
        { path: 'reservations', component: () => import('../views/Reservations.vue') },
        { path: 'locks', component: () => import('../views/Locks.vue') },
        { path: 'deal-mappings', component: () => import('../views/DealMappings.vue') },
        { path: 'coupons', component: () => import('../views/Coupons.vue') },
        { path: 'seats', component: () => import('../views/Seats.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('admin_token')
  if (to.path !== '/login' && !token) return '/login'
})

export default router
