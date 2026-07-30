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
  { to: '/endorsements', label: 'Endorsements' },
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
  <header class="sticky top-0 z-sticky p-4 text-white bg-forest shadow-strong">
    <div class="max-w-[960px] mx-auto relative flex flex-wrap items-start justify-between gap-3">
      <h1 class="sr-only">{{ title }}</h1>
      <div class="logo-container">
        <RouterLink to="/" aria-label="Vote for Julia Home" @click="closeMenu">
          <Image
            url-endpoint="https://ik.imagekit.io/voteforjulia"
            src="/julia-hamann-for-mankato-mayor.avif"
            alt="Julia Hamann for Mankato Mayor"
            class="w-[200px] h-auto"
            sizes="200px"
            :image-breakpoints="[200, 400]"
            :device-breakpoints="[]"
            width="200"
            height="95"
            crossorigin="anonymous"
            fetchpriority="high"
            loading="eager"
            decoding="async"
          />
        </RouterLink>
      </div>
      <button
        class="menu-toggle block bg-mint rounded-md border-none cursor-pointer py-[1.35rem] px-4 ml-auto z-floating"
        :aria-label="showMenu ? 'Close menu' : 'Open menu'"
        :aria-expanded="showMenu"
        aria-controls="main-menu"
        @click="toggleMenu"
      >
        <span
          class="block relative w-7 h-[3px] bg-forest rounded-xs before:content-[''] before:absolute before:left-0 before:w-7 before:h-[3px] before:bg-forest before:rounded-xs before:transition-all before:duration-300 before:-top-[9px] after:content-[''] after:absolute after:left-0 after:w-7 after:h-[3px] after:bg-forest after:rounded-xs after:transition-all after:duration-300 after:top-[9px]"
        ></span>
      </button>

      <nav aria-label="Main navigation">
        <Transition name="menu">
          <ul
            v-show="showMenu"
            id="main-menu"
            class="flex list-none absolute top-[-6px] right-[6px] w-[220px] flex-col bg-leaf rounded-lg py-4 shadow-[0_8px_24px_rgb(0_0_0/0.15)] z-dropdown"
            :class="{ open: showMenu }"
          >
            <li v-for="link in navLinks" :key="link.label">
              <RouterLink
                :to="link.to"
                class="text-white font-action font-semibold tracking-[0.08em] flex px-4 py-2"
                @click="closeMenu"
                >{{ link.label }}</RouterLink
              >
            </li>
            <li>
              <RouterLink
                to="/donate"
                class="font-action font-semibold tracking-[0.08em] rounded-pill pt-[0.7rem] pb-2 px-4 shadow-soft flex bg-white text-fern hover:bg-white/85 mx-3 my-1 justify-center"
                @click="handleDonateClick"
                >Donate</RouterLink
              >
            </li>
            <li class="flex items-center justify-center gap-2.5 text-2xl text-white px-4 py-2 mt-2">
              <a
                href="https://www.instagram.com/voteforjuliahamann"
                aria-label="Julia on Instagram"
                class="text-white inline-flex"
                target="_blank"
                rel="noopener noreferrer"
                ><IconInstagram
              /></a>
              <a
                href="https://www.facebook.com/profile.php?id=61590411090366"
                aria-label="Julia on Facebook"
                class="text-white inline-flex"
                target="_blank"
                rel="noopener noreferrer"
                ><IconFacebook
              /></a>
            </li>
          </ul>
        </Transition>
      </nav>
    </div>
  </header>
</template>
