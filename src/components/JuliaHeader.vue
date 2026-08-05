<script setup lang="ts">
import { ref } from 'vue';
import { RouterLink, type RouteLocationRaw } from 'vue-router';
import { Image } from '@imagekit/vue';
import JuliaButton from './JuliaButton.vue';
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
  <header class="sticky top-0 z-sticky bg-forest p-4 text-white shadow-strong">
    <div class="relative mx-auto flex max-w-[960px] flex-wrap items-start justify-between gap-3">
      <h1 class="sr-only">{{ title }}</h1>
      <div class="logo-container">
        <RouterLink to="/" aria-label="Vote for Julia Home" @click="closeMenu">
          <Image
            url-endpoint="https://ik.imagekit.io/voteforjulia"
            src="/julia-hamann-for-mankato-mayor.avif"
            alt="Julia Hamann for Mankato Mayor"
            class="h-auto w-[200px]"
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
        class="menu-toggle z-floating ml-auto block cursor-pointer rounded-md border-none bg-mint px-4 py-[1.35rem]"
        :aria-label="showMenu ? 'Close menu' : 'Open menu'"
        :aria-expanded="showMenu"
        aria-controls="main-menu"
        @click="toggleMenu"
      >
        <span
          class="relative block h-[3px] w-7 rounded-xs bg-forest before:absolute before:-top-[9px] before:left-0 before:h-[3px] before:w-7 before:rounded-xs before:bg-forest before:transition-all before:duration-300 before:content-[''] after:absolute after:top-[9px] after:left-0 after:h-[3px] after:w-7 after:rounded-xs after:bg-forest after:transition-all after:duration-300 after:content-['']"
        ></span>
      </button>

      <nav aria-label="Main navigation">
        <Transition name="menu">
          <ul
            v-show="showMenu"
            id="main-menu"
            class="absolute top-[-6px] right-[6px] z-dropdown flex w-[220px] list-none flex-col rounded-lg bg-leaf py-4 shadow-[0_8px_24px_rgb(0_0_0/0.15)]"
            :class="{ open: showMenu }"
          >
            <li v-for="link in navLinks" :key="link.label">
              <RouterLink
                :to="link.to"
                class="flex px-4 py-2 font-action font-semibold tracking-[0.08em] text-white"
                @click="closeMenu"
                >{{ link.label }}</RouterLink
              >
            </li>
            <!-- flex-col so the inline-flex button stretches to the menu width
                 the way its block-level predecessor did. -->
            <li class="mx-3 my-1 flex flex-col">
              <JuliaButton
                variant="secondary"
                class="tracking-[0.08em]"
                to="/donate"
                @click="handleDonateClick"
                >Donate</JuliaButton
              >
            </li>
            <li class="mt-2 flex items-center justify-center gap-2.5 px-4 py-2 text-2xl text-white">
              <a
                href="https://www.instagram.com/voteforjuliahamann"
                aria-label="Julia on Instagram"
                class="inline-flex text-white"
                target="_blank"
                rel="noopener noreferrer"
                ><IconInstagram
              /></a>
              <a
                href="https://www.facebook.com/profile.php?id=61590411090366"
                aria-label="Julia on Facebook"
                class="inline-flex text-white"
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
