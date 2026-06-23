import type { RouteRecordRaw } from 'vue-router';

export const routes: RouteRecordRaw[] = [
  { path: '/', component: () => import('../pages/JuliaHome.vue') },
  { path: '/meet-julia', component: () => import('../pages/JuliaAbout.vue') },
  { path: '/volunteer', component: () => import('../pages/JuliaVolunteer.vue') },
  { path: '/secret-recipe', component: () => import('../pages/JuliaSecretRecipe.vue') },
  { path: '/donate', component: () => import('../pages/JuliaDonate.vue') }
];
