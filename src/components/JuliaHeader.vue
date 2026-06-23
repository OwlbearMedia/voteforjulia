<script setup lang="ts">
import { ref } from 'vue';
import { RouterLink } from 'vue-router';
import { Image } from '@imagekit/vue';
import IconInstagram from './icons/IconInstagram.vue';
import IconFacebook from './icons/IconFacebook.vue';
import { trackDonateClick } from '../lib/analytics';

defineOptions({
  name: 'JuliaHeader'
});

const { title } = defineProps<{
  title: string;
}>();

const showMenu = ref(false);

function toggleMenu() {
  showMenu.value = !showMenu.value;
}

function closeMenu() {
  showMenu.value = false;
}

function handleDonateClick() {
  trackDonateClick('header', 'Donate');
  closeMenu();
}
</script>

<template>
  <header class="bg-julia-dark-green">
    <div class="container">
      <h1 class="sr-only">{{ title }}</h1>
      <div class="logo-container">
        <a href="/" aria-label="Vote for Julia Home">
          <Image
            url-endpoint="https://ik.imagekit.io/voteforjulia"
            src="/julia-hamann-for-mankato-mayor.avif"
            alt="Julia Hamann for Mankato Mayor"
            class="logo"
            sizes="200px"
            :image-breakpoints="[200, 400]"
            :device-breakpoints="[]"
            width="200"
            height="97"
            crossorigin="anonymous"
            fetchpriority="high"
            loading="eager"
            decoding="async"
          />
        </a>
      </div>
      <button
        class="menu-toggle"
        aria-label="Open menu"
        :aria-expanded="showMenu"
        aria-controls="main-menu"
        @click="toggleMenu"
      >
        <span class="hamburger"></span>
      </button>

      <nav aria-label="Main navigation">
        <ul id="main-menu" class="menu-list" :class="{ open: showMenu }">
          <li><RouterLink to="/" @click="closeMenu">Home</RouterLink></li>
          <li><RouterLink to="/meet-julia" @click="closeMenu">Meet Julia</RouterLink></li>
          <li>
            <RouterLink :to="{ path: '/', hash: '#issues' }" @click="closeMenu">Issues</RouterLink>
          </li>
          <li><RouterLink to="/volunteer" @click="closeMenu">Volunteer</RouterLink></li>
          <li>
            <RouterLink to="/donate" class="donate" @click="handleDonateClick">Donate</RouterLink>
          </li>
          <li class="social-icons">
            <a
              href="https://www.instagram.com/voteforjuliahamann"
              aria-label="Julia on Instagram"
              target="_blank"
              rel="noopener noreferrer"
              ><IconInstagram
            /></a>
            <a
              href="https://www.facebook.com/profile.php?id=61590411090366"
              aria-label="Julia on Facebook"
              target="_blank"
              rel="noopener noreferrer"
              ><IconFacebook
            /></a>
          </li>
        </ul>
      </nav>
    </div>
  </header>
</template>
