<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { trackDonateClick, trackFooterIconClick } from '../lib/analytics';
import IconInstagram from './icons/IconInstagram.vue';
import IconFacebook from './icons/IconFacebook.vue';
import IconEnvelope from './icons/IconEnvelope.vue';

defineOptions({
  name: 'JuliaFooter'
});

// Tailwind's scanner reads these string literals like any template text.
const BTN_BASE =
  'inline-block pt-3 pb-2 px-6 font-action font-semibold rounded-pill shadow-soft hover:no-underline';
const BTN = `${BTN_BASE} bg-leaf text-white hover:bg-sprout/70`;
const BTN_INVERT = `${BTN_BASE} bg-white text-fern mr-4 hover:bg-white/85`;

function handleFooterIconClick(href: string, ariaLabel: string) {
  trackFooterIconClick(href, ariaLabel);
}

function handleDonateClick() {
  trackDonateClick('footer', 'Donate');
}

const footerSupportActionsAnchorRef = ref<HTMLElement | null>(null);
const footerSupportActionsRef = ref<HTMLElement | null>(null);
const footerSupportActionsHeight = ref(0);
const isFooterSupportActionsFixed = ref(false);

let footerSupportActionsResizeObserver: ResizeObserver | null = null;
let safeAreaBottomInsetCache: number | null = null;
let safeAreaProbeEl: HTMLDivElement | null = null;
let footerSupportActionsRafId: number | null = null;

function getSafeAreaProbeElement() {
  if (safeAreaProbeEl) {
    return safeAreaProbeEl;
  }

  const probe = document.createElement('div');
  probe.setAttribute('aria-hidden', 'true');
  probe.style.position = 'fixed';
  probe.style.left = '0';
  probe.style.bottom = '0';
  probe.style.visibility = 'hidden';
  probe.style.pointerEvents = 'none';
  probe.style.paddingBottom = 'env(safe-area-inset-bottom)';

  document.body.appendChild(probe);
  safeAreaProbeEl = probe;

  return safeAreaProbeEl;
}

function getSafeAreaBottomInset() {
  if (safeAreaBottomInsetCache !== null) {
    return safeAreaBottomInsetCache;
  }

  if (typeof document === 'undefined') {
    return 0;
  }

  const probe = getSafeAreaProbeElement();
  const safeArea = Number.parseFloat(getComputedStyle(probe).paddingBottom);
  safeAreaBottomInsetCache = Number.isFinite(safeArea) ? safeArea : 0;

  return safeAreaBottomInsetCache;
}

function updateFooterSupportActionsState() {
  const anchorEl = footerSupportActionsAnchorRef.value;
  const actionsEl = footerSupportActionsRef.value;

  if (!anchorEl || !actionsEl) {
    isFooterSupportActionsFixed.value = false;
    return;
  }

  const isMobileViewport =
    typeof globalThis.matchMedia === 'function'
      ? globalThis.matchMedia('(max-width: 700px)').matches
      : false;

  if (!isMobileViewport) {
    isFooterSupportActionsFixed.value = false;
    return;
  }

  footerSupportActionsHeight.value = actionsEl.offsetHeight;

  const bottomOffset = 16 + getSafeAreaBottomInset();
  const anchorRect = anchorEl.getBoundingClientRect();
  const fixedTop = globalThis.innerHeight - bottomOffset - footerSupportActionsHeight.value;

  isFooterSupportActionsFixed.value = anchorRect.top > fixedTop;
}

function scheduleFooterSupportActionsStateUpdate() {
  if (footerSupportActionsRafId !== null) {
    return;
  }

  if (typeof globalThis.requestAnimationFrame === 'function') {
    footerSupportActionsRafId = globalThis.requestAnimationFrame(() => {
      footerSupportActionsRafId = null;
      updateFooterSupportActionsState();
    });
    return;
  }

  updateFooterSupportActionsState();
}

function handleResize() {
  safeAreaBottomInsetCache = null;
  scheduleFooterSupportActionsStateUpdate();
}

onMounted(() => {
  updateFooterSupportActionsState();

  window.addEventListener('scroll', scheduleFooterSupportActionsStateUpdate, {
    passive: true
  });
  window.addEventListener('resize', handleResize);

  if (typeof ResizeObserver !== 'undefined' && footerSupportActionsRef.value) {
    footerSupportActionsResizeObserver = new ResizeObserver(() => {
      scheduleFooterSupportActionsStateUpdate();
    });

    footerSupportActionsResizeObserver.observe(footerSupportActionsRef.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('scroll', scheduleFooterSupportActionsStateUpdate);
  window.removeEventListener('resize', handleResize);
  footerSupportActionsResizeObserver?.disconnect();

  if (footerSupportActionsRafId !== null && typeof globalThis.cancelAnimationFrame === 'function') {
    globalThis.cancelAnimationFrame(footerSupportActionsRafId);
    footerSupportActionsRafId = null;
  }

  if (safeAreaProbeEl) {
    safeAreaProbeEl.remove();
    safeAreaProbeEl = null;
  }
});
</script>

<template>
  <footer
    class="py-6 px-8 bg-forest shadow-strong-up backdrop-blur-[4px] motion-reduce:backdrop-blur-none text-center text-[0.875rem] text-white"
  >
    <div class="grid grid-cols-2 max-desktop:grid-cols-1 gap-6 max-w-[960px] mx-auto">
      <div class="max-desktop:row-start-2">
        <p class="font-accent text-[1.25rem]">Follow Julia's Campaign</p>
        <div class="flex items-center justify-center gap-[0.6rem] text-[1.5rem] text-white">
          <a
            href="https://www.instagram.com/voteforjuliahamann"
            aria-label="Julia on Instagram"
            class="text-white"
            target="_blank"
            rel="noopener noreferrer"
            @click="
              handleFooterIconClick(
                'https://www.instagram.com/voteforjuliahamann',
                'Julia on Instagram'
              )
            "
            ><IconInstagram
          /></a>
          <a
            href="https://www.facebook.com/profile.php?id=61590411090366"
            aria-label="Julia on Facebook"
            class="text-white"
            target="_blank"
            rel="noopener noreferrer"
            @click="
              handleFooterIconClick(
                'https://www.facebook.com/profile.php?id=61590411090366',
                'Julia on Facebook'
              )
            "
            ><IconFacebook
          /></a>
          <a
            href="mailto:info@voteforjulia.com"
            class="text-white"
            aria-label="Email Julia"
            @click="handleFooterIconClick('mailto:info@voteforjulia.com', 'Email Julia')"
            ><IconEnvelope
          /></a>
        </div>
      </div>
      <div class="footer-support max-desktop:row-start-1">
        <p class="font-accent text-[1.25rem]">Support Julia's Campaign</p>
        <div
          ref="footerSupportActionsAnchorRef"
          class="footer-support-actions-anchor flex justify-center"
        >
          <div
            ref="footerSupportActionsRef"
            class="footer-support-actions inline-flex items-center"
            :class="{
              'footer-support-actions-hidden invisible pointer-events-none':
                isFooterSupportActionsFixed
            }"
            :aria-hidden="isFooterSupportActionsFixed ? 'true' : undefined"
            :inert="isFooterSupportActionsFixed ? true : undefined"
          >
            <RouterLink :class="BTN_INVERT" to="/volunteer">Volunteer</RouterLink>
            <RouterLink :class="BTN" to="/donate" @click="handleDonateClick">Donate</RouterLink>
          </div>
        </div>
      </div>
      <div class="col-span-2 mt-4">
        Paid for by Julia Hamann for Mankato Mayor<br />
        PO Box 4051, Mankato, MN 56002
      </div>
      <div class="col-span-2 mt-4"></div>
    </div>
  </footer>

  <Teleport to="body">
    <div
      v-if="isFooterSupportActionsFixed"
      class="fixed left-0 right-0 bottom-0 h-[calc(5rem_+_var(--safe-area-inset-bottom))] bg-forest shadow-strong-up z-[1090] pointer-events-none"
      aria-hidden="true"
    ></div>
    <div
      v-if="isFooterSupportActionsFixed"
      class="footer-support-actions footer-support-actions-fixed inline-flex items-center fixed left-1/2 -translate-x-1/2 bottom-[calc(1rem_+_var(--safe-area-inset-bottom))] z-[1100]"
    >
      <RouterLink :class="BTN_INVERT" to="/volunteer">Volunteer</RouterLink>
      <RouterLink :class="BTN" to="/donate" @click="handleDonateClick">Donate</RouterLink>
    </div>
  </Teleport>
</template>
