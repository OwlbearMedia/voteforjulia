<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { trackDonateClick, trackFooterIconClick } from '../lib/analytics';
import JuliaButton from './JuliaButton.vue';
import IconInstagram from './icons/IconInstagram.vue';
import IconFacebook from './icons/IconFacebook.vue';
import IconEnvelope from './icons/IconEnvelope.vue';

defineOptions({
  name: 'JuliaFooter'
});

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
      ? globalThis.matchMedia('(width < 48rem)').matches
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
    class="bg-forest px-8 py-6 text-center text-sm text-white shadow-strong-up backdrop-blur-[4px] motion-reduce:backdrop-blur-none"
  >
    <div class="mx-auto grid max-w-[960px] grid-cols-2 gap-6 max-md:grid-cols-1">
      <div class="max-md:row-start-2">
        <p class="font-accent text-xl">Follow Julia's Campaign</p>
        <div class="flex items-center justify-center gap-2.5 text-2xl text-white">
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
      <div class="footer-support max-md:row-start-1">
        <p class="font-accent text-xl">Support Julia's Campaign</p>
        <div
          ref="footerSupportActionsAnchorRef"
          class="footer-support-actions-anchor flex justify-center"
        >
          <div
            ref="footerSupportActionsRef"
            class="footer-support-actions inline-flex items-center"
            :class="{
              'footer-support-actions-hidden pointer-events-none invisible':
                isFooterSupportActionsFixed
            }"
            :aria-hidden="isFooterSupportActionsFixed ? 'true' : undefined"
            :inert="isFooterSupportActionsFixed ? true : undefined"
          >
            <JuliaButton variant="secondary" class="mr-4" to="/volunteer">Volunteer</JuliaButton>
            <JuliaButton to="/donate" @click="handleDonateClick">Donate</JuliaButton>
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
      class="pointer-events-none fixed right-0 bottom-0 left-0 z-overlay h-[calc(5rem_+_var(--safe-area-inset-bottom))] bg-forest shadow-strong-up"
      aria-hidden="true"
    ></div>
    <div
      v-if="isFooterSupportActionsFixed"
      class="footer-support-actions footer-support-actions-fixed fixed bottom-[calc(1rem_+_var(--safe-area-inset-bottom))] left-1/2 z-floating inline-flex -translate-x-1/2 items-center"
    >
      <JuliaButton variant="secondary" class="mr-4" to="/volunteer">Volunteer</JuliaButton>
      <JuliaButton to="/donate" @click="handleDonateClick">Donate</JuliaButton>
    </div>
  </Teleport>
</template>
