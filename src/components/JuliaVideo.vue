<script setup lang="ts">
import { computed } from 'vue';

defineOptions({
  name: 'JuliaVideo'
});

const props = defineProps<{
  /** The id from the share link: `bc4dvZpAa-A` in `youtu.be/bc4dvZpAa-A`. */
  videoId: string;
  /** What a screen reader announces for the frame, so name the specific video. */
  title: string;
}>();

// Fixed here, never passed in: it is the origin frame-src allows, and
// embedOrigins.spec.ts checks it by rendering. See docs/conventions.md,
// "Embedded iframes".
const EMBED_ORIGIN = 'https://www.youtube-nocookie.com';

const src = computed(() => `${EMBED_ORIGIN}/embed/${props.videoId}`);
</script>

<template>
  <iframe
    class="aspect-video w-full rounded-lg shadow-soft"
    :src="src"
    :title="title"
    loading="lazy"
    allow="
      accelerometer;
      autoplay;
      clipboard-write;
      encrypted-media;
      gyroscope;
      picture-in-picture;
      web-share;
    "
    referrerpolicy="strict-origin-when-cross-origin"
    allowfullscreen
  ></iframe>
</template>
