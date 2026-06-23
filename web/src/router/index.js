import { createRouter, createWebHistory } from 'vue-router'
import ProjectList from '@/views/ProjectList.vue'
import AcceptanceLayout from '@/views/AcceptanceLayout.vue'

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
      component: AcceptanceLayout,
    },
  ],
})

export default router
