<script setup lang="ts">
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';
import JuliaHeader from './components/JuliaHeader.vue';
import JuliaFooter from './components/JuliaFooter.vue';

const route = useRoute();

const pageHeaderTitle = computed(() => {
  const routeTitles: Record<string, string> = {
    '/meet-julia': 'Get to Know Julia Hamann — Mankato Mayor Candidate',
    '/volunteer': "Join Julia’s Team — Volunteer in Mankato",
    '/donate': "Support Julia Hamann’s Campaign for Mankato Mayor",
    '/events': 'Upcoming Campaign Events — Julia Hamann for Mankato Mayor',
    '/secret-recipe': "Julia’s Famous Shrimp Salad Supreme Recipe"
  };

  return routeTitles[route.path] ?? 'Elect Julia Hamann — A New Voice for Mankato';
});
</script>

<template>
  <JuliaHeader :title="pageHeaderTitle" />
  <main>
    <RouterView />
  </main>
  <JuliaFooter />
</template>
