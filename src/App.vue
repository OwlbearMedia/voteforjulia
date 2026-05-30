<script setup lang="ts">
import { RouterView } from 'vue-router';
import JuliaHeader from './components/JuliaHeader.vue';
import JuliaFooter from './components/JuliaFooter.vue';
</script>

<template>
  <JuliaHeader title="Julia Hamann for Mankato Mayor" />
  <main>
    <RouterView />
  </main>
  <JuliaFooter />
</template>
