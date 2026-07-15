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
  <footer>
    <div class="footer-container">
      <div>
        <p class="bigger">Follow Julia's Campaign</p>
        <div class="social-icons">
          <a
            href="https://www.instagram.com/voteforjuliahamann"
            aria-label="Julia on Instagram"
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
            href="mailto:info@juliahamann.com"
            aria-label="Email Julia"
            @click="handleFooterIconClick('mailto:info@juliahamann.com', 'Email Julia')"
            ><IconEnvelope
          /></a>
        </div>
      </div>
      <div class="footer-support">
        <p class="bigger">Support Julia's Campaign</p>
        <div ref="footerSupportActionsAnchorRef" class="footer-support-actions-anchor">
          <div
            ref="footerSupportActionsRef"
            class="footer-support-actions"
            :class="{
              'footer-support-actions-hidden': isFooterSupportActionsFixed
            }"
            :aria-hidden="isFooterSupportActionsFixed ? 'true' : undefined"
            :inert="isFooterSupportActionsFixed ? true : undefined"
          >
            <RouterLink class="btn btn-invert" to="/volunteer">Volunteer</RouterLink>
            <RouterLink class="btn" to="/donate" @click="handleDonateClick">Donate</RouterLink>
          </div>
        </div>
      </div>
      <div class="footer-disclaimer">
        Paid for by Julia Hamann for Mankato Mayor<br>
        PO Box 4051, Mankato, MN 56002
      </div>
      <div class="footer-disclaimer "> </div>
    </div>
  </footer>

  <Teleport to="body">
    <div
      v-if="isFooterSupportActionsFixed"
      class="footer-support-actions-fixed-backdrop"
      aria-hidden="true"
    ></div>
    <div
      v-if="isFooterSupportActionsFixed"
      class="footer-support-actions footer-support-actions-fixed"
    >
      <RouterLink class="btn btn-invert" to="/volunteer">Volunteer</RouterLink>
      <RouterLink class="btn" to="/donate" @click="handleDonateClick">Donate</RouterLink>
    </div>
  </Teleport>
</template>
