import JuliaHome from '../pages/JuliaHome.vue';
import JuliaAbout from '../pages/JuliaAbout.vue';
import JuliaVolunteer from '../pages/JuliaVolunteer.vue';
import JuliaSecretRecipe from '../pages/JuliaSecretRecipe.vue';
import JuliaDonate from '../pages/JuliaDonate.vue';

export const routes = [
  { path: '/', component: JuliaHome, alias: '/index.html' },
  { path: '/meet-julia', component: JuliaAbout, alias: '/meet-julia.html' },
  { path: '/volunteer', component: JuliaVolunteer, alias: '/volunteer.html' },
  { path: '/secret-recipe', component: JuliaSecretRecipe, alias: '/secret-recipe.html' },
  { path: '/donate', component: JuliaDonate, alias: '/donate.html' },
];
