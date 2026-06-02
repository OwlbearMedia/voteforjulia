import JuliaHome from '../pages/JuliaHome.vue';
import JuliaAbout from '../pages/JuliaAbout.vue';
import JuliaVolunteer from '../pages/JuliaVolunteer.vue';
import JuliaSecretRecipe from '../pages/JuliaSecretRecipe.vue';
import JuliaDonate from '../pages/JuliaDonate.vue';

export const routes = [
  { path: '/', component: JuliaHome },
  { path: '/meet-julia', component: JuliaAbout },
  { path: '/volunteer', component: JuliaVolunteer },
  { path: '/secret-recipe', component: JuliaSecretRecipe },
  { path: '/donate', component: JuliaDonate },
];
