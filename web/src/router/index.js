import { createRouter, createWebHistory } from 'vue-router'
import ProjectList from '@/views/ProjectList.vue'
import AcceptanceDetail from '@/views/AcceptanceDetail.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: ProjectList,
    },
    {
      path: '/acceptance/:name',
      name: 'acceptance',
      component: AcceptanceDetail,
    },
  ],
})

export default router
