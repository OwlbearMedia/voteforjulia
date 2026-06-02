<script setup lang="ts">
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
        <RouterLink class="btn btn-invert" to="/volunteer"
          >Volunteer</RouterLink
        >
        <RouterLink class="btn" to="/donate" @click="handleDonateClick"
          >Donate</RouterLink
        >
      </div>
      <div class="footer-disclaimer">
        Paid for by Julia Hamann for Mankato Mayor
      </div>
      <div class="footer-disclaimer-address">
        311 N 5th St. Mankato MN 56001
      </div>
    </div>
  </footer>
</template>
