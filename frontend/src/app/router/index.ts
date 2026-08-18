import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/HomePage.vue'),
    },
    {
      path: '/shops',
      name: 'shops',
      component: () => import('@/pages/shops/ShopCenterPage.vue'),
    },
  ],
})

export default router
