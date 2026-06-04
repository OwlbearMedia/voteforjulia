<script setup lang="ts">
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';
import JuliaHeader from './components/JuliaHeader.vue';
import JuliaFooter from './components/JuliaFooter.vue';

const route = useRoute();

const pageHeaderTitle = computed(() => {
  const routeTitles: Record<string, string> = {
    '/meet-julia': 'Meet Julia | Julia Hamann for Mankato Mayor',
    '/volunteer': 'Volunteer | Julia Hamann for Mankato Mayor',
    '/donate': 'Donate | Julia Hamann for Mankato Mayor',
    '/secret-recipe': 'Secret Recipe | Julia Hamann for Mankato Mayor'
  };

  return routeTitles[route.path] ?? 'Julia Hamann for Mankato Mayor';
});
</script>

<template>
  <JuliaHeader :title="pageHeaderTitle" />
  <main>
    <RouterView />
  </main>
  <JuliaFooter />
</template>
