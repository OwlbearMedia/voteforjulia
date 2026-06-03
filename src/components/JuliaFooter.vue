<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { faEnvelope } from "@fortawesome/free-regular-svg-icons";
import { faInstagram, faFacebookF } from "@fortawesome/free-brands-svg-icons";
import { trackDonateClick, trackFooterIconClick } from "../lib/analytics";

defineOptions({
  name: "JuliaFooter",
});

function handleFooterIconClick(href: string, ariaLabel: string) {
  trackFooterIconClick(href, ariaLabel);
}

function handleDonateClick() {
  trackDonateClick("footer", "Donate");
}

const footerSupportActionsAnchorRef = ref<HTMLElement | null>(null);
const footerSupportActionsRef = ref<HTMLElement | null>(null);
const footerSupportActionsHeight = ref(0);
const isFooterSupportActionsFixed = ref(false);

let footerSupportActionsResizeObserver: ResizeObserver | null = null;

function updateFooterSupportActionsState() {
  const anchorEl = footerSupportActionsAnchorRef.value;
  const actionsEl = footerSupportActionsRef.value;

  if (!anchorEl || !actionsEl) {
    isFooterSupportActionsFixed.value = false;
    return;
  }

  footerSupportActionsHeight.value = actionsEl.offsetHeight;

  if (!globalThis.matchMedia("(max-width: 700px)").matches) {
    isFooterSupportActionsFixed.value = false;
    return;
  }

  const anchorRect = anchorEl.getBoundingClientRect();
  const fixedTop =
    globalThis.innerHeight - 16 - footerSupportActionsHeight.value;

  isFooterSupportActionsFixed.value = anchorRect.top > fixedTop;
}

onMounted(() => {
  updateFooterSupportActionsState();

  window.addEventListener("scroll", updateFooterSupportActionsState, {
    passive: true,
  });
  window.addEventListener("resize", updateFooterSupportActionsState);

  if (typeof ResizeObserver !== "undefined" && footerSupportActionsRef.value) {
    footerSupportActionsResizeObserver = new ResizeObserver(() => {
      updateFooterSupportActionsState();
    });

    footerSupportActionsResizeObserver.observe(footerSupportActionsRef.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", updateFooterSupportActionsState);
  window.removeEventListener("resize", updateFooterSupportActionsState);
  footerSupportActionsResizeObserver?.disconnect();
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
                'Julia on Instagram',
              )
            "
            ><FontAwesomeIcon :icon="faInstagram"
          /></a>
          <a
            href="https://www.facebook.com/profile.php?id=61590411090366"
            aria-label="Julia on Facebook"
            target="_blank"
            rel="noopener noreferrer"
            @click="
              handleFooterIconClick(
                'https://www.facebook.com/profile.php?id=61590411090366',
                'Julia on Facebook',
              )
            "
            ><FontAwesomeIcon :icon="faFacebookF"
          /></a>
          <a
            href="mailto:info@juliahamann.com"
            aria-label="Email Julia"
            @click="
              handleFooterIconClick(
                'mailto:info@juliahamann.com',
                'Email Julia',
              )
            "
            ><FontAwesomeIcon :icon="faEnvelope"
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
              'footer-support-actions-hidden': isFooterSupportActionsFixed,
            }"
            :aria-hidden="isFooterSupportActionsFixed ? 'true' : undefined"
          >
            <RouterLink class="btn btn-invert" to="/volunteer"
              >Volunteer</RouterLink
            >
            <RouterLink class="btn" to="/donate" @click="handleDonateClick"
              >Donate</RouterLink
            >
          </div>
        </div>
      </div>
      <div class="footer-disclaimer">
        Paid for by Julia Hamann for Mankato Mayor
      </div>
      <div class="footer-disclaimer-address">
        311 N 5th St. Mankato MN 56001
      </div>
    </div>
  </footer>

  <Teleport to="body">
    <div v-if="isFooterSupportActionsFixed" class="footer-support-actions-fixed-backdrop"></div>
    <div v-if="isFooterSupportActionsFixed" class="footer-support-actions footer-support-actions-fixed">
      <RouterLink class="btn btn-invert" to="/volunteer">Volunteer</RouterLink>
      <RouterLink class="btn" to="/donate" @click="handleDonateClick">Donate</RouterLink>
    </div>
  </Teleport>
</template>
