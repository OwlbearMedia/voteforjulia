<script setup lang="ts">
import { ref } from 'vue';
import { RouterLink, type RouteLocationRaw } from 'vue-router';
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

const navLinks: { to: RouteLocationRaw; label: string }[] = [
  { to: '/', label: 'Home' },
  { to: '/meet-julia', label: 'Meet Julia' },
  { to: { path: '/', hash: '#issues' }, label: 'Issues' },
  { to: '/events', label: 'Events' },
  { to: '/volunteer', label: 'Volunteer' },
  { to: '/yard-signs', label: 'Yard Signs' }
];

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
  <header
    class="sticky top-0 z-[1000] px-8 text-white bg-forest backdrop-blur-[4px] shadow-strong max-desktop:p-4 max-desktop:backdrop-blur-none motion-reduce:backdrop-blur-none"
  >
    <div
      class="max-w-[960px] mx-auto flex flex-wrap items-center justify-between gap-6 px-8 py-4 max-desktop:relative max-desktop:items-start max-desktop:gap-3 max-desktop:p-0"
    >
      <h1 class="sr-only">{{ title }}</h1>
      <div class="logo-container">
        <a href="/" aria-label="Vote for Julia Home">
          <Image
            url-endpoint="https://ik.imagekit.io/voteforjulia"
            src="/julia-hamann-for-mankato-mayor.avif"
            alt="Julia Hamann for Mankato Mayor"
            class="w-50 h-auto"
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
        class="menu-toggle hidden max-desktop:block bg-mint rounded-md border-none cursor-pointer py-[1.35rem] px-4 ml-auto z-[1100]"
        aria-label="Open menu"
        :aria-expanded="showMenu"
        aria-controls="main-menu"
        @click="toggleMenu"
      >
        <span
          class="block relative w-7 h-[3px] bg-forest rounded-[2px] before:content-[''] before:absolute before:left-0 before:w-7 before:h-[3px] before:bg-forest before:rounded-[2px] before:transition-all before:duration-300 before:-top-[9px] after:content-[''] after:absolute after:left-0 after:w-7 after:h-[3px] after:bg-forest after:rounded-[2px] after:transition-all after:duration-300 after:top-[9px]"
        ></span>
      </button>

      <nav aria-label="Main navigation">
        <ul
          id="main-menu"
          class="items-center gap-4 list-none max-desktop:absolute max-desktop:top-[47px] max-desktop:right-[10px] max-desktop:w-[220px] max-desktop:flex-col max-desktop:gap-0 max-desktop:bg-leaf max-desktop:rounded-b-lg max-desktop:py-4 max-desktop:shadow-[0_8px_24px_rgb(0_0_0/0.15)] max-desktop:z-[1001]"
          :class="showMenu ? 'open flex' : 'hidden desktop:flex'"
        >
          <li v-for="link in navLinks" :key="link.label">
            <RouterLink
              :to="link.to"
              class="text-white font-action font-semibold tracking-[0.08em] max-desktop:flex max-desktop:px-4 max-desktop:py-2"
              @click="closeMenu"
              >{{ link.label }}</RouterLink
            >
          </li>
          <li>
            <RouterLink
              to="/donate"
              class="text-white font-action font-semibold tracking-[0.08em] rounded-pill pt-[0.7rem] pb-2 px-4 shadow-soft desktop:bg-leaf max-desktop:flex max-desktop:bg-white max-desktop:text-fern max-desktop:hover:bg-white/85 max-desktop:mx-3 max-desktop:my-1 max-desktop:justify-center"
              @click="handleDonateClick"
              >Donate</RouterLink
            >
          </li>
          <li
            class="desktop:hidden flex items-center justify-center gap-[0.6rem] text-[1.5rem] text-white max-desktop:px-4 max-desktop:py-2 max-desktop:mt-2"
          >
            <a
              href="https://www.instagram.com/voteforjuliahamann"
              aria-label="Julia on Instagram"
              class="text-white max-desktop:inline-flex"
              target="_blank"
              rel="noopener noreferrer"
              ><IconInstagram
            /></a>
            <a
              href="https://www.facebook.com/profile.php?id=61590411090366"
              aria-label="Julia on Facebook"
              class="text-white max-desktop:inline-flex"
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
