import type { RouteRecordRaw } from 'vue-router';
import { appRoutePaths } from './routePaths';

const pageImports: Record<(typeof appRoutePaths)[number], () => Promise<unknown>> = {
  '/': () => import('../pages/JuliaHome.vue'),
  '/meet-julia': () => import('../pages/JuliaAbout.vue'),
  '/volunteer': () => import('../pages/JuliaVolunteer.vue'),
  '/secret-recipe': () => import('../pages/JuliaSecretRecipe.vue'),
  '/donate': () => import('../pages/JuliaDonate.vue'),
  '/events': () => import('../pages/JuliaEvents.vue')
};

export const routes: RouteRecordRaw[] = appRoutePaths.map((path) => ({
  path,
  component: pageImports[path]
}));
