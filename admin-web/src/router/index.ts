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
        { path: 'stores', component: () => import('../views/Stores.vue') },
        { path: 'pricing', component: () => import('../views/Pricing.vue') },
        { path: 'seats', component: () => import('../views/Seats.vue') },
        { path: 'reservations', component: () => import('../views/Reservations.vue') },
        { path: 'card-purchase-orders', component: () => import('../views/CardPurchaseOrders.vue') },
        { path: 'users', component: () => import('../views/Users.vue') },
        { path: 'period-cards', component: () => import('../views/PeriodCards.vue') },
        { path: 'exchange-records', component: () => import('../views/ExchangeRecords.vue') },
        { path: 'wallet-logs', component: () => import('../views/WalletLogs.vue') },
        { path: 'study-data', component: () => import('../views/StudyData.vue') },
        { path: 'knowledge', component: () => import('../views/Knowledge.vue') },
        { path: 'system-status', component: () => import('../views/SystemStatus.vue') },
        { path: 'banners', component: () => import('../views/Banners.vue') },
        { path: 'announcements', component: () => import('../views/Announcements.vue') },
        { path: 'store-calendar', component: () => import('../views/StoreCalendar.vue') },
        { path: 'operation-logs', component: () => import('../views/OperationLogs.vue') },
        { path: 'point-logs', component: () => import('../views/PointLogs.vue') },
        { path: 'invites', component: () => import('../views/Invites.vue') },
        { path: 'admins', component: () => import('../views/Admins.vue') },
        { path: 'locks', component: () => import('../views/Locks.vue') },
        { path: 'deal-mappings', component: () => import('../views/DealMappings.vue') },
        { path: 'coupons', component: () => import('../views/Coupons.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('admin_token')
  if (to.path !== '/login' && !token) return '/login'
})

export default router
